"""Deterministic JSON transport stub. Does not call or simulate an AI model."""
import json
import sys

request = json.load(sys.stdin)
prompt = request['messages'][-1]['content']
records = json.loads(prompt.rsplit('\n', 1)[-1])
fields = request['schema']['properties']['results']['items']['properties']
field = next(key for key in fields if key != 'case_id')
response = {'results': [
    {'case_id': record['case_id'], field: 'MOCK_TRANSPORT_ONLY_NOT_A_PREDICTION'}
    for record in records
]}
json.dump({'response': response, 'usage': {}, 'model': 'DETERMINISTIC_STUB_NOT_A_MODEL'}, sys.stdout)
