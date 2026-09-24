"""Generic, evaluator-owned faults; no inspection of private protocol bodies."""
import copy
import hashlib

NODES = ('source', 'gateway', 'A', 'B')
DOMAIN = 'reservation-seeded-audit-v1'

def hash_int(text):
    return int.from_bytes(hashlib.sha256(text.encode('ascii')).digest(), 'big')

def config(index):
    if type(index) is not int or not 0 <= index < 20:
        raise ValueError('index outside frozen 20-seed pack')
    seed = hashlib.sha256(f'{DOMAIN}:seed:{index}'.encode('ascii')).hexdigest()
    links = [(a,b) for a in NODES for b in NODES if a != b]
    return {'version': DOMAIN, 'index': index, 'seed': seed,
            'split': 'calibration' if index < 4 else 'evaluation',
            'template_index': index % 4,
            'link': list(links[hash_int(seed + ':link') % len(links)]),
            'link_start_round': 9 + hash_int(seed + ':link_start') % 8,
            'link_duration_rounds': 2,
            'output_node': NODES[hash_int(seed + ':output_node') % len(NODES)],
            'output_eligible_ordinal': 1 + hash_int(seed + ':output_ordinal') % 3,
            'output_round_intervals': [[9,21],[32,59]]}

class SchedulePolicy:
    def __init__(self, supplied=None):
        self.config = copy.deepcopy(supplied)
        if supplied is not None and supplied != config(supplied.get('index')):
            raise ValueError('schedule config differs from frozen generator')
        self.nonempty_outputs = 0
        self.output_trigger = None
        self.link_matches = self.additional_link_deferrals = 0
        self.permuted_rounds = self.permuted_packets = 0

    def order_queue(self, queue, round_number, priorities):
        if self.config is None:
            return sorted(queue, key=lambda item: priorities[item[1]])
        self.permuted_rounds += 1
        self.permuted_packets += len(queue)
        seed = self.config['seed']
        # Original insertion index breaks even a theoretical digest collision.
        indexed = sorted(enumerate(queue), key=lambda pair: (hash_int(f'{seed}:queue:{round_number}:{pair[0]}'),pair[0]))
        return [item for _,item in indexed]

    def block_link(self, round_number, src, dst, already_blocked=False):
        c = self.config
        active = bool(c and [src,dst] == c['link'] and c['link_start_round'] <= round_number < c['link_start_round']+c['link_duration_rounds'])
        if active:
            self.link_matches += 1
            self.additional_link_deferrals += not already_blocked
        return active

    def drop_output(self, round_number, logical_step, node, output):
        c = self.config
        if not c or self.output_trigger is not None or node != c['output_node']:
            return False
        if not any(lo <= round_number <= hi for lo,hi in c['output_round_intervals']):
            return False
        if not (output['messages'] or output['replies']):
            return False
        self.nonempty_outputs += 1
        if self.nonempty_outputs != c['output_eligible_ordinal']:
            return False
        self.output_trigger = {'round':round_number,'step':logical_step,'node':node,
                               'messages':len(output['messages']),'replies':len(output['replies'])}
        return True

    def report(self):
        return {'config':copy.deepcopy(self.config), 'permuted_rounds':self.permuted_rounds,
                'permuted_packets':self.permuted_packets, 'link_matches':self.link_matches,
                'additional_link_deferrals':self.additional_link_deferrals,
                'eligible_output_batches_seen':self.nonempty_outputs,
                'output_trigger':copy.deepcopy(self.output_trigger)}
