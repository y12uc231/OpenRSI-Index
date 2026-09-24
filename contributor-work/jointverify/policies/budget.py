"""Thread-safe call/check limits plus honest token and tool-time accounting."""
from __future__ import annotations

from copy import deepcopy
import math
import threading


class BudgetExceeded(RuntimeError):
    pass


class TelemetryError(ValueError):
    pass


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TelemetryError(f'{name} must be a nonnegative integer.')
    return value


def normalize_usage(usage):
    """OpenAI/Codex-style inclusive input/output totals; no reasoning double count.

    Other providers must normalize their accounting semantics before calling
    this function. In particular Anthropic cache reads/writes are not silently
    assumed to already be included in its differently defined input_tokens.
    """
    if not isinstance(usage, dict):
        raise TelemetryError('Usage telemetry is missing or malformed.')
    if any(k in usage for k in ('cache_read_input_tokens', 'cache_creation_input_tokens')):
        raise TelemetryError('Normalize provider-specific cache accounting first.')

    def aliases(names):
        values = [_integer(usage[name], name) for name in names if name in usage]
        if not values or any(v != values[0] for v in values):
            raise TelemetryError('Missing or inconsistent token totals.')
        return values[0]

    input_tokens = aliases(('input_tokens', 'prompt_tokens'))
    output_tokens = aliases(('output_tokens', 'completion_tokens'))
    total = input_tokens + output_tokens
    if 'total_tokens' in usage and _integer(usage['total_tokens'], 'total_tokens') != total:
        raise TelemetryError('total_tokens does not equal inclusive input + output.')
    reasoning = []
    if 'reasoning_tokens' in usage:
        reasoning.append(_integer(usage['reasoning_tokens'], 'reasoning_tokens'))
    for key in ('output_tokens_details', 'completion_tokens_details'):
        if key in usage:
            if not isinstance(usage[key], dict):
                raise TelemetryError('Malformed output detail telemetry.')
            if 'reasoning_tokens' in usage[key]:
                reasoning.append(_integer(usage[key]['reasoning_tokens'], 'reasoning_tokens'))
    if reasoning and (max(reasoning) > output_tokens or len(set(reasoning)) != 1):
        raise TelemetryError('Reasoning tokens must be a consistent output subset.')
    cached = []
    if 'cached_input_tokens' in usage:
        cached.append(_integer(usage['cached_input_tokens'], 'cached_input_tokens'))
    for key in ('input_tokens_details', 'prompt_tokens_details'):
        if key in usage:
            if not isinstance(usage[key], dict):
                raise TelemetryError('Malformed input detail telemetry.')
            if 'cached_tokens' in usage[key]:
                cached.append(_integer(usage[key]['cached_tokens'], 'cached_tokens'))
    if cached and (max(cached) > input_tokens or len(set(cached)) != 1):
        raise TelemetryError('Cached tokens must be a consistent input subset.')
    return {'input_tokens': input_tokens, 'output_tokens': output_tokens,
            'total_tokens': total, 'reasoning_tokens': reasoning[0] if reasoning else None,
            'cached_input_tokens': cached[0] if cached else None}


class BudgetLedger:
    def __init__(self, max_calls=20, max_checks=4, max_total_tokens=None, max_tool_seconds=None):
        self.max_calls = _integer(max_calls, 'max_calls')
        self.max_checks = _integer(max_checks, 'max_checks')
        self.max_total_tokens = None if max_total_tokens is None else _integer(max_total_tokens, 'max_total_tokens')
        if max_tool_seconds is not None and (isinstance(max_tool_seconds, bool) or
                not isinstance(max_tool_seconds, (float, int)) or not math.isfinite(max_tool_seconds) or max_tool_seconds < 0):
            raise ValueError('max_tool_seconds must be finite and nonnegative.')
        self.max_tool_seconds = max_tool_seconds
        self.calls = []
        self.tools = []
        self.known_total_tokens = 0
        self.token_telemetry_valid = True
        self.tool_telemetry_valid = True
        self.tool_seconds = 0.0
        self.overrun = False
        self._lock = threading.RLock()

    def reserve_call(self, input_upper_bound=None, output_token_limit=None, require_bounded=None):
        """Reserve before launch. Bounds must cover all context/reasoning tokens.

        The caller must actually enforce output_token_limit at the provider.
        With no hard output cap (e.g. local Codex CLI), use call-count mode and
        leave both bounds absent; the ledger will not claim token parity.
        """
        with self._lock:
            if len(self.calls) >= self.max_calls or self.overrun:
                raise BudgetExceeded('Model call budget exhausted or an overrun occurred.')
            if self.max_total_tokens is not None and not self.token_telemetry_valid:
                raise TelemetryError('Token-budget continuation blocked by missing telemetry.')
            bounded = input_upper_bound is not None and output_token_limit is not None
            if (input_upper_bound is None) != (output_token_limit is None):
                raise ValueError('Supply both token bounds, or neither.')
            reserve = None
            if bounded:
                reserve = _integer(input_upper_bound, 'input_upper_bound') + _integer(output_token_limit, 'output_token_limit')
            require_bounded = self.max_total_tokens is not None if require_bounded is None else require_bounded
            if require_bounded and not bounded:
                raise BudgetExceeded('A hard token budget requires enforceable per-call bounds.')
            pending = sum(c['reserved_tokens'] or 0 for c in self.calls if c['status'] == 'reserved')
            if self.max_total_tokens is not None and self.known_total_tokens + pending + (reserve or 0) > self.max_total_tokens:
                raise BudgetExceeded('Insufficient remaining tokens for the reservation.')
            ticket = len(self.calls)
            self.calls.append({'ticket': ticket, 'status': 'reserved', 'reserved_tokens': reserve,
                               'input_upper_bound': input_upper_bound, 'output_token_limit': output_token_limit})
            return ticket

    def settle_call(self, ticket, usage):
        with self._lock:
            call = self.calls[ticket]
            if call['status'] != 'reserved':
                raise ValueError('Call already settled.')
            try:
                normalized = normalize_usage(usage)
            except TelemetryError:
                call['status'] = 'invalid_telemetry'
                call['usage'] = None
                self.token_telemetry_valid = False
                raise
            call.update(status='settled', usage=normalized)
            self.known_total_tokens += normalized['total_tokens']
            if call['reserved_tokens'] is not None and (
                    normalized['input_tokens'] > call['input_upper_bound'] or
                    normalized['output_tokens'] > call['output_token_limit']):
                self.overrun = True
                call['status'] = 'reservation_exceeded'
            if self.max_total_tokens is not None and self.known_total_tokens > self.max_total_tokens:
                self.overrun = True
            if self.overrun:
                raise BudgetExceeded('Observed usage exceeded its declared bound; do not claim budget compliance.')
            return deepcopy(normalized)

    def start_tool(self, is_check=False):
        """Reserve a public-check slot before starting it; ordinary tools also count time."""
        with self._lock:
            if not isinstance(is_check, bool):
                raise ValueError('is_check must be a boolean.')
            if is_check and sum(t['is_check'] for t in self.tools) >= self.max_checks:
                raise BudgetExceeded('Public joint-check budget exhausted.')
            if self.max_tool_seconds is not None and (not self.tool_telemetry_valid or self.tool_seconds >= self.max_tool_seconds):
                raise BudgetExceeded('Tool-time budget exhausted or unmeasurable.')
            ticket = len(self.tools)
            self.tools.append({'ticket': ticket, 'is_check': is_check, 'status': 'running', 'seconds': None})
            return ticket

    def finish_tool(self, ticket, seconds):
        with self._lock:
            tool = self.tools[ticket]
            if tool['status'] != 'running':
                raise ValueError('Tool already settled.')
            if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not math.isfinite(seconds) or seconds < 0:
                tool['status'] = 'invalid_telemetry'
                self.tool_telemetry_valid = False
                raise TelemetryError('Tool elapsed time must be finite and nonnegative.')
            tool.update(status='completed', seconds=float(seconds))
            self.tool_seconds += seconds
            if self.max_tool_seconds is not None and self.tool_seconds > self.max_tool_seconds:
                self.overrun = True
                raise BudgetExceeded('Tool-time budget exceeded; actual tool timeouts must be enforced by the runner.')

    def summary(self):
        with self._lock:
            complete = all(c['status'] != 'reserved' for c in self.calls)
            tokens_valid = self.token_telemetry_valid and complete
            tools_complete = all(t['status'] != 'running' for t in self.tools)
            return {'calls_started': len(self.calls), 'max_calls': self.max_calls,
                    'public_checks_started': sum(t['is_check'] for t in self.tools), 'max_checks': self.max_checks,
                    'total_tokens': self.known_total_tokens if tokens_valid else None,
                    'known_reported_tokens': self.known_total_tokens,
                    'token_telemetry_valid': tokens_valid,
                    'token_budget_mode': 'bounded_reservations' if self.max_total_tokens is not None and
                        all(c['reserved_tokens'] is not None for c in self.calls) else 'call_count_only_tokens_diagnostic',
                    'max_total_tokens': self.max_total_tokens,
                    'total_tool_seconds': self.tool_seconds if self.tool_telemetry_valid and tools_complete else None,
                    'max_tool_seconds': self.max_tool_seconds,
                    'overrun': self.overrun, 'calls': deepcopy(self.calls), 'tools': deepcopy(self.tools)}
