"""Exercise a local agent model and record timings, tool calls and GPU allocation."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from check_services import json_request, load_dotenv
from mcp_client import MCPClient


def benchmark(model, base, galaxus=False):
    native = base.rstrip('/').removesuffix('/v1')
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": model,
              "ollama_version": json_request(native + '/api/version').get('version'), "tests": []}

    def request(label, path, payload, record=True):
        start = time.monotonic()
        response = json_request(native + path, payload, timeout=120)
        result = {"name": label, "seconds": round(time.monotonic() - start, 3)}
        if response.get('eval_duration'):
            result['tokens_per_second'] = round(response['eval_count'] / (response['eval_duration'] / 1e9), 2)
            result['output_tokens'] = response['eval_count']
            result['prompt_tokens'] = response.get('prompt_eval_count')
        if record:
            report['tests'].append(result)
        print(f"{label}: {result['seconds']} s", flush=True)
        return response, result

    response, result = request('Deutsch', '/api/chat', {
        "model": model, "stream": False, "think": False,
        "messages": [{"role": "user", "content":
            "Erklaere auf Deutsch in hoechstens zwei Saetzen, wie du bei der Auswahl eines Smart-Home-Geraets unter CHF 150 hilfst. Erfinde keine konkreten Produkte."}],
        "options": {"temperature": 0, "num_predict": 160},
    })
    result['answer'] = response['message']['content']
    result['passed'] = bool(result['answer'].strip())

    filler = '\n'.join(f'Testnotiz {i}: Dies ist neutraler Fuelltext fuer die Kontextpruefung.'
                       for i in range(500))
    response, result = request('Langer Eingangskontext', '/api/chat', {
        "model": model, "stream": False, "think": False,
        "messages": [{"role": "user", "content":
            "Die fiktive Testkennung lautet LOTUS-7429. Merke sie dir.\n" + filler
            + "\nNenne ausschliesslich die Testkennung vom Anfang dieses Textes."}],
        "options": {"temperature": 0, "num_predict": 40},
    })
    result['answer'] = response['message']['content']
    result['passed'] = 'LOTUS-7429' in result['answer']

    for iteration in range(3):
        response, result = request(f'Werkzeugaufruf {iteration + 1}', '/v1/chat/completions', {
            "model": model, "stream": False, "temperature": 0, "max_tokens": 100,
            "reasoning_effort": "none",
            "messages": [{"role": "user", "content": "Call the ping tool with value OK."}],
            "tools": [{"type": "function", "function": {
                "name": "ping", "description": "Connectivity test",
                "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                               "required": ["value"]},
            }}],
        })
        calls = response['choices'][0]['message'].get('tool_calls', [])
        result['calls'] = calls
        result['passed'] = any(c.get('function', {}).get('name') == 'ping'
            and json.loads(c['function']['arguments']).get('value') == 'OK' for c in calls)

    schema = {"type": "object", "properties": {
        "budget_chf": {"type": "integer"},
        "interests": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "string"}},
    }, "required": ["budget_chf", "interests", "avoid"], "additionalProperties": False}
    response, result = request('Strukturierte Vorlieben', '/v1/chat/completions', {
        "model": model, "stream": False, "temperature": 0, "max_tokens": 250,
        "reasoning_effort": "none",
        "messages": [{"role": "user", "content":
            "Extrahiere diese fiktiven Test-Vorlieben als JSON: Budget CHF 149, Interessen Smart Home und Technik, vermeiden: Cloud-Abos."}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "preferences", "strict": True, "schema": schema}},
    })
    parsed = json.loads(response['choices'][0]['message']['content'])
    result['answer'] = parsed
    result['passed'] = (parsed.get('budget_chf') == 149 and bool(parsed.get('interests'))
                        and bool(parsed.get('avoid')))

    if galaxus:
        client = MCPClient(os.getenv('GALAXUS_MCP_URL', 'https://mcp.galaxus.ch'))
        client.initialize()
        tool = next(t for t in client.request('tools/list')['tools'] if t['name'] == 'search_products')
        payload = {
            "model": model, "stream": False, "temperature": 0, "max_tokens": 300,
            "reasoning_effort": "none",
            "messages": [{"role": "user", "content":
                f'Dein Agent heisst Milo und nutzt {model} ueber Ollama. '
                'Suche jetzt drei Smart-Home-Produkte unter CHF 150 auf Deutsch mit search_products.'}],
            "tools": [{"type": "function", "function": {
                "name": tool['name'], "description": tool['description'],
                "parameters": tool['inputSchema'],
            }}],
        }
        guide = Path(__file__).resolve().parent.parent / 'prompts' / 'shopping-guide.md'
        if guide.exists():
            payload['messages'].insert(0, {'role': 'system',
                'content': guide.read_text(encoding='utf-8').replace('{{MODEL}}', model)})
        result = {"name": "Galaxus-MCP mit Servervalidierung", "attempts": [], "passed": False}
        report['tests'].append(result)
        for attempt_number in range(2):
            response, attempt = request(f'Galaxus-Aufruf {attempt_number + 1}',
                '/v1/chat/completions', payload, record=False)
            message = response['choices'][0]['message']
            calls = message.get('tool_calls', [])
            attempt['calls'] = calls
            result['attempts'].append(attempt)
            call = next((c for c in calls if c.get('function', {}).get('name') == 'search_products'), None)
            if call is None:
                attempt['error'] = 'Kein search_products-Aufruf'
                break
            try:
                actual = client.request('tools/call', {'name': 'search_products',
                    'arguments': json.loads(call['function']['arguments'])})
                attempt['mcp_result'] = actual
                if actual.get('isError'):
                    raise RuntimeError(json.dumps(actual))
                result['passed'] = True
                break
            except RuntimeError as exc:
                attempt['error'] = str(exc)
                payload['messages'].extend([
                    {'role': 'assistant', 'content': message.get('content') or '',
                     'tool_calls': [{k: v for k, v in c.items() if k != 'index'} for c in calls]},
                    {'role': 'tool', 'tool_call_id': call['id'], 'content': json.dumps({'error': str(exc)})},
                ])
        result['seconds'] = round(sum(a['seconds'] for a in result['attempts']), 3)

    loaded = json_request(native + '/api/ps')
    report['loaded_models'] = [{key: m.get(key) for key in
        ['name', 'digest', 'size', 'size_vram', 'context_length', 'details']} for m in loaded.get('models', [])]
    report['passed'] = all(t['passed'] for t in report['tests'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', help='Candidate model (defaults to .env)')
    parser.add_argument('--with-galaxus', action='store_true', help='Also test the live Galaxus tool schema')
    parser.add_argument('--output', type=Path, default=Path('.runtime/benchmarks/model.json'))
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    report = benchmark(args.model or os.environ['OLLAMA_MODEL'], os.environ['OLLAMA_BASE_URL'], args.with_galaxus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
