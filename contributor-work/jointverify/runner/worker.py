"""Private-container coding worker driven by auditable JSON actions.

The local Codex model has no tools or repository mount. It receives only the
worker's feature brief and explicit tool observations. Commands execute in a
network-disabled Docker container through a controller-owned gateway.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

ACTION_SCHEMA = {
    'type':'object',
    'properties': {key:{'type':'string'} for key in ('action','command','message','summary')},
    'required':['action','command','message','summary'], 'additionalProperties':False,
}

INSTRUCTIONS = '''You are one of two software engineers implementing separate requested features in the same repository.
You have a private working tree. Your teammate has another private working tree based on the same commit.
Your joint objective is that BOTH requested features work in the combined patch. Existing behavior must remain correct.
Analyze and edit the code, add focused tests when useful, run public tests, and coordinate about dependencies.
Send useful information to your teammate through the message field. Messages can accompany a shell command.
Describe your planned files and interfaces early. Ask concrete questions if another change may interact.
Your teammate's current patch is available at /tmp/jointverify-peer.patch; it is a snapshot, not automatically applied.
You may inspect or integrate that patch when useful. Do not assume it is fresh beyond its attached revision hash.
You can use ordinary programming, scripts, git, tests, and structured messages. No internet is available.
Use only the feature brief and visible repository. Do not seek evaluation assets or reference patches.

You do NOT have direct tool access. Return exactly one JSON action object:
{"action":"shell|message|finish","command":"...","message":"...","summary":"short progress/status"}.
For shell, command is executed in bash at /workspace/repo in your isolated container. You may combine related operations.
Use heredocs for multiline files; do not change unrelated behavior. Commands start with a fresh shell; filesystem changes persist.
For message or finish, command must be empty. message is broadcast to the teammate (empty is allowed).
Use finish only when your implementation and checks are complete. A failed joint check can reopen your work for repair.
The controller will combine the workers' patches and run public integration checks at selected points.
Public-check feedback is evidence, not proof of passing the final independently supplied feature tests.
No hidden feature tests or reference implementation are supplied to you.
'''


def shell(argv, *, data=None, timeout=120, check=False):
    p=subprocess.run(argv,input=data,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f'Controller command failed: {argv[0:2]}: {p.stderr[-1500:]}')
    return p


class PrivateContainer:
    def __init__(self,image,role,*,cpus=2,memory='2g',command_seconds=90):
        self.name='jointverify-'+role+'-'+uuid.uuid4().hex[:10]
        self.image=image
        self.command_seconds=command_seconds
        self.closed=False
        shell(['docker','run','-d','--name',self.name,'--network','none','--cpus',str(cpus),
               '--memory',memory,'--pids-limit','192','--cap-drop','ALL',
               '--security-opt','no-new-privileges','--entrypoint','sleep',image,'infinity'],check=True)
        try:
            self.original_base=shell(['docker','exec',self.name,'git','-C','/workspace/repo','rev-parse','HEAD'],check=True).stdout.strip()
            original_tree=shell(['docker','exec',self.name,'git','-C','/workspace/repo','rev-parse','HEAD^{tree}'],check=True).stdout.strip()
            tracked=shell(['docker','exec',self.name,'git','-C','/workspace/repo','ls-files','-z'],check=True).stdout
            # Upstream images may retain later Git history. Reinitialize only
            # this private container; force-add formerly tracked ignored files.
            shell(['docker','exec',self.name,'python','-c',
                   'import shutil;shutil.rmtree("/workspace/repo/.git")'],check=True)
            shell(['docker','exec',self.name,'git','-C','/workspace/repo','init'],check=True)
            shell(['docker','exec','-i',self.name,'git','-C','/workspace/repo','add','--force',
                   '--pathspec-from-file=-','--pathspec-file-nul'],data=tracked,check=True)
            actual_tree=shell(['docker','exec',self.name,'git','-C','/workspace/repo','write-tree'],check=True).stdout.strip()
            if actual_tree!=original_tree:
                raise RuntimeError('Reinitialized worker tree differs from pinned original tree')
            shell(['docker','exec',self.name,'git','-C','/workspace/repo','-c','user.name=JointVerify Base',
                   '-c','user.email=baseline@invalid.example','commit','-m','Pinned task starting snapshot'],check=True)
            self.base=shell(['docker','exec',self.name,'git','-C','/workspace/repo','rev-parse','HEAD'],check=True).stdout.strip()
            self.write('/tmp/jointverify-peer.patch','')
        except Exception:
            self.close()
            raise

    def write(self,path,content):
        shell(['docker','exec','-i',self.name,'python','-c',
               'import sys;open(sys.argv[1],"w").write(sys.stdin.read())',path],data=content,check=True)

    def execute(self,command):
        start=time.monotonic()
        p=shell(['docker','exec',self.name,'timeout','--signal=KILL',str(self.command_seconds),
                 'bash','-lc','cd /workspace/repo && '+command],timeout=self.command_seconds+15)
        return {'exit_code':p.returncode,'stdout':p.stdout[-24000:], 'stderr':p.stderr[-6000:],
                'stdout_truncated':len(p.stdout)>24000,'stderr_truncated':len(p.stderr)>6000,
                'wall_seconds':round(time.monotonic()-start,3)}

    def patch(self):
        # Include untracked files, retaining private git changes only inside the container.
        shell(['docker','exec',self.name,'git','-C','/workspace/repo','add','-A'],check=True)
        return shell(['docker','exec',self.name,'git','-C','/workspace/repo','diff',
                      '--cached','--binary','--no-ext-diff',self.base],check=True).stdout

    def close(self):
        if not self.closed:
            shell(['docker','rm','-f',self.name])
            self.closed=True


@dataclass
class Worker:
    worker_id: str
    feature: str
    container: PrivateContainer
    history: list=field(default_factory=list)
    turns: int=0
    done: bool=False
    revision: str=''
    latest_patch: str=''

    def prompt(self,peer_revision,remaining):
        # Cap only old command-output context. Never modify source briefs or message history.
        # Truncation is explicit in the prompt and logged in the run's observation record.
        entries=[]
        chars=0
        for entry in reversed(self.history):
            encoded=json.dumps(entry)
            if chars+len(encoded)>80000 and entry.get('kind')=='tool':
                entries.append({'kind':'tool','observation':'[Older command output omitted by fixed 80k-character context policy.]'})
            else:
                entries.append(entry); chars+=len(encoded)
        entries.reverse()
        return (INSTRUCTIONS+f'\nYou are {self.worker_id}. Team calls remaining: {remaining}. '
                f'Current teammate patch revision: {peer_revision or "empty"}.\n'
                f'YOUR FEATURE:\n{self.feature}\nEXPLICIT HISTORY:\n'+json.dumps(entries))

    def accept(self,response):
        if (not isinstance(response,dict) or set(response)!=set(ACTION_SCHEMA['required'])
                or any(not isinstance(v,str) for v in response.values())):
            raise ValueError('Malformed worker action object')
        if response['action'] not in {'shell','message','finish'}:
            raise ValueError('Unknown worker action')
        if response['action']!='shell' and response['command']:
            raise ValueError('Non-shell action supplied a command')
        if response['action']=='shell' and not response['command'].strip():
            raise ValueError('Empty shell action')
        self.turns+=1
        self.history.append({'kind':'action',**response})
        observation=None
        if response['action']=='shell':
            observation=self.container.execute(response['command'])
            self.history.append({'kind':'tool',**observation})
        self.done=response['action']=='finish'
        self.latest_patch=self.container.patch()
        self.revision=hashlib.sha256(self.latest_patch.encode()).hexdigest()
        return observation
