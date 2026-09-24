"""Trusted CPU environment/policy engine; controller code is never mounted here."""
import argparse,base64,contextlib,hashlib,json,os,pathlib,re,resource,shutil,sys,time
from wire import read,write


class ControllerFailure(Exception):
    def __init__(self, status, code, error_type):
        self.status=status if status in ('candidate_invalid','infrastructure_or_incomplete') else 'infrastructure_or_incomplete'
        clean=lambda value: value if isinstance(value,str) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,63}',value) else 'invalid_diagnostic'
        self.code=clean(code);self.error_type=clean(error_type)

def controller_response(stream):
    response=read(stream)
    if isinstance(response,dict) and set(response)=={'error'} and isinstance(response['error'],dict):
        e=response['error'];raise ControllerFailure(e.get('status'),e.get('code'),e.get('error_type'))
    return response

def main():
    # Capture protocol FD, then redirect even native/import-time stdout to diagnostics.
    output=os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    with contextlib.redirect_stdout(sys.stderr):
        parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=('dev','evaluation'),required=True);parser.add_argument('--proof-first-world',action='store_true');args=parser.parse_args()
        worlds=list(range(20000,20004)) if args.suite=='dev' else list(range(9999,10019))
        if args.proof_first_world: worlds=worlds[:1]
        started=time.monotonic();steps_limit=10000;world_id=worlds[0]
        shutil.copytree('/app/alem','/tmp/alem')
        sys.path[:0]=['/tmp','/app/baselines']
        import jax,jax.numpy as jnp,numpy as np,yaml,distrax
        import utils,ippo_hypermarl_rnn as trainer
        from alem.alem_coop.alem_state import StaticEnvParams
        from alem.alem_coop.action_masking import compute_action_mask
        from alem.alem_coop.envs.common import compute_score
        with open('/app/baselines/config/hypermarl_rnn.yaml') as h:config=yaml.safe_load(h)
        with open('/assets/1B/hypermarl-rnn/hard/seed0/config.json') as h:release=json.load(h)
        config.update(release['reload_overrides'])
        config.update(SCALE_BASE_DIFFICULTY=False,APPEND_AGENT_ID=True,TRAINING_COORDINATION_DIFFICULTY='hard')
        shape_keys=['APPEND_AGENT_ID','GRU_HIDDEN_DIM','FC_DIM_SIZE','ACTIVATION','HYPERNET_EMBEDDING_DIM','HYPERNET_HIDDEN_DIMS','HYPERNET_INIT_SCALE','USE_AGENT_ID_EMBEDDINGS','USE_BIAS_IN_HYPERNET','ACTION_MASKING','NUM_COMM_CHANNELS']
        for key in shape_keys:
            if config[key]!=release['training_config'][key]:raise ValueError('checkpoint shape mismatch: '+key)
        env=utils._make_eval_env(config,'Alem-Coop-Symbolic','hard',StaticEnvParams(num_comm_channels=4))
        params=utils.restore_baseline_checkpoint('/assets/1B/hypermarl-rnn/hard/seed0/checkpoint')['params']
        obs_dim=env.observation_space(env.agents[0]).shape[0]
        action_dim=env.action_space(env.agents[0]).n
        network=trainer.ActorCriticRNN(action_dim,config=config,num_agents=env.num_agents,observation_dim=obs_dim)
        initial_h=trainer.ScannedRNN.initialize_carry(env.num_agents,config['GRU_HIDDEN_DIM'])
        @jax.jit
        def predict(state,obs,hstate,dones):
            batch=jnp.stack([obs[a] for a in env.agents])
            next_h,pi,_=network.apply(params,hstate,(batch[None,:],dones[None,:]))
            mask=compute_action_mask(state,env.default_params,env.static_env_params)
            logits=pi.logits+jnp.where(mask[None,:,:],0.0,-1e10)
            proposal=distrax.Categorical(logits=logits).mode()[0]
            return next_h,batch,mask,logits[0],proposal
        @jax.jit
        def advance(state,actions,rng):
            # Same three-way split as native sequential evaluator; episode start differs explicitly.
            next_rng,action_rng,step_rng=jax.random.split(rng,3)
            obs,state,reward,done,_=env.step_env(step_rng,state,{a:actions[i] for i,a in enumerate(env.agents)})
            return obs,state,jnp.stack([reward[a] for a in env.agents]),jnp.stack([done[a] for a in env.agents]),done['__all__'],next_rng
        def fingerprint(tree):
            leaves,structure=jax.tree.flatten(tree)
            h=hashlib.sha256(str(structure).encode())
            for leaf in leaves:
                arr=np.asarray(leaf);h.update(str(arr.dtype).encode());h.update(str(arr.shape).encode());h.update(arr.tobytes())
            return h.hexdigest()
        def array(x,dtype):
            arr=np.asarray(x,dtype='<f4' if dtype=='f4' else np.uint8)
            return {'dtype':dtype,'size':int(arr.size),'data':base64.b64encode(arr.tobytes()).decode('ascii')}
        def scalar_metrics(state):
            metrics={}
            utils._flatten_user_info_prefix('',compute_score(state,jnp.array(True),env.static_env_params),metrics)
            return metrics
        def reset(world_id):
            obs,state=env.reset(jax.random.PRNGKey(world_id))
            rng=jax.random.fold_in(jax.random.PRNGKey(0xA1E00001),world_id)
            return obs,state,initial_h,jnp.zeros(env.num_agents,dtype=bool),rng
        write(output,{'kind':'milestone','name':'restored','seconds':time.monotonic()-started})
        obs,state,h,dones,rng=reset(worlds[0]);compile_start=time.monotonic()
        prediction=jax.block_until_ready(predict(state,obs,h,dones))
        jax.block_until_ready(advance(state,prediction[-1],rng))
        compile_seconds=time.monotonic()-compile_start
        schema={'observation_size':obs_dim,'action_count':action_dim,'native_comm_action_ids':list(range(action_dim-4,action_dim)),'max_memory_bytes':65536}
        def rollout(world_id):
            begin=time.monotonic();traces=[];ipc_seconds=0.;overrides=native_comm=completed=forward_batches=calls_started=0
            failure=None;done=False
            try:
                write(output,{'kind':'initialize','world_id':world_id,'schema':schema,'actors':3})
                response=controller_response(sys.stdin.buffer)
                if response!={'ready':True}:raise ControllerFailure('infrastructure_or_incomplete','initialization_protocol','ProtocolError')
                obs,state,h,dones,rng=reset(world_id);prev=np.zeros(3,dtype=np.float32)
                for step in range(steps_limit):
                    h,batch,mask,logits,proposal=jax.block_until_ready(predict(state,obs,h,dones))
                    forward_batches+=1
                    tick=time.monotonic()
                    packets=[{'observation':array(batch[i],'f4'),'legal_mask':array(mask[i],'u1'),'frozen_logits':array(logits[i],'f4'),'proposal':int(proposal[i]),'previous_reward':float(prev[i]),'step':step} for i in range(3)]
                    write(output,{'kind':'actions','packets':packets})
                    calls_started+=3
                    try:
                        response=controller_response(sys.stdin.buffer)
                    finally:
                        ipc_seconds+=time.monotonic()-tick
                    if not isinstance(response,dict) or set(response)!={'actions'} or not isinstance(response['actions'],list) or len(response['actions'])!=3:
                        raise ControllerFailure('infrastructure_or_incomplete','joint_action_protocol','ProtocolError')
                    for i,a in enumerate(response['actions']):
                        if type(a)is not int or not 0<=a<action_dim or not bool(mask[i,a]):
                            raise ControllerFailure('candidate_invalid','illegal_action','InvalidAction')
                    actions=np.asarray(response['actions'],dtype=np.int32)
                    overrides+=int(np.sum(actions!=np.asarray(proposal)))
                    native_comm+=int(np.sum(actions>=action_dim-4))
                    obs,state,prev,dones,done,rng=advance(state,jnp.asarray(actions),rng)
                    traces.append(fingerprint((state,obs,h,actions,prev,dones,rng)))
                    completed+=1
                    if bool(done):break
            except ControllerFailure as exc:
                failure=exc
            metrics=scalar_metrics(state) if failure is None else {}
            return {'world_id':world_id,'status':failure.status if failure else 'scored',
                    'steps':completed,'naturally_terminated':bool(done),
                    'score':metrics.get('Team/coord_reward_pct_of_max') if failure is None else None,
                    'metrics':metrics,'diagnostic_code':failure.code if failure else None,
                    'error_type':failure.error_type if failure else None,
                    'seconds':time.monotonic()-begin,'ipc_seconds':ipc_seconds,
                    'overrides':overrides,'action_count':completed*3,
                    'policy_forward_batches':forward_batches,'controller_calls':calls_started,
                    'native_communication_actions':native_comm,
                    'trace_sha256':hashlib.sha256(''.join(traces).encode()).hexdigest()}
        result={'schema_version':1,'status':'running','suite':args.suite,'world_ids':worlds,'total':len(worlds),'scored':0,'primary_score':None,'metrics_mean':None,'cases':[],
                'source_sha':'14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e','weights_revision':'9493179ea5e86cd625add66c0f88e23f04f928b5',
                'checkpoint':'1B/hypermarl-rnn/hard/seed0','config':config,
                'rng_rule':'reset=PRNGKey(world_id); transition=fold_in(PRNGKey(0xA1E00001),world_id); native three-way split each step',
                'schema':schema,'versions':{'jax':jax.__version__,'numpy':np.__version__},
                'compile_warmup_seconds':compile_seconds,
                'scope':'fixed world set; decentralized frozen RL policy augmentation; candidate-only evaluation with public canonical evaluation worlds'}
        output_path=pathlib.Path('/results/engine-result.private.json')
        def save():
            result['python_wall_seconds']=time.monotonic()-started
            result['peak_rss_kib_linux']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            output_path.write_text(json.dumps(result,indent=2)+'\n')
        save()
        try:
            for world_id in worlds:
                row=rollout(world_id);result['cases'].append(row)
                result['scored']=sum(c['status']=='scored' for c in result['cases']);save()
                write(output,{'kind':'world_result','world_id':world_id,'result':row})
        except Exception:
            done_worlds={c['world_id'] for c in result['cases']}
            for missing in worlds:
                if missing not in done_worlds:
                    result['cases'].append({'world_id':missing,'status':'infrastructure_or_incomplete','score':None,'metrics':{},'diagnostic_code':'engine_interrupted','error_type':'EngineError','steps':0,'naturally_terminated':False})
            result['status']='unscored';save();raise
        result['status']='scored' if result['scored']==len(worlds) else 'unscored'
        if result['status']=='scored':
            result['primary_score']=sum(c['score'] for c in result['cases'])/len(worlds)
            keys=set(result['cases'][0]['metrics'])
            if not all(set(c['metrics'])==keys for c in result['cases']):raise ValueError('metric keys differ')
            result['metrics_mean']={k:sum(c['metrics'][k] for c in result['cases'])/len(worlds) for k in sorted(keys)}
        save()
        write(output,{'kind':'done','status':result['status'],'total':result['total'],'scored':result['scored']})

if __name__=='__main__':main()
