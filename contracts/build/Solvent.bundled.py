# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import hashlib
import ipaddress
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import genlayer as gl
from genlayer.storage import TreeMap
from genlayer.types import Address, u256
DECISION_FULL = 'FULL'
DECISION_HALF = 'HALF'
DECISION_NONE = 'NONE'
DECISION_INCONCLUSIVE = 'INCONCLUSIVE'
VALID_DECISIONS = {DECISION_FULL, DECISION_HALF, DECISION_NONE, DECISION_INCONCLUSIVE}
UNIT_ACTIVE = 'ACTIVE'
UNIT_EXPIRED = 'EXPIRED'
UNIT_CLAIMED_FULL = 'CLAIMED_FULL'
UNIT_CLAIMED_HALF = 'CLAIMED_HALF'
CLAIM_OPEN = 'OPEN'
CLAIM_APPROVED = 'APPROVED'
CLAIM_DENIED = 'DENIED'
CLAIM_INCONCLUSIVE = 'INCONCLUSIVE'
CLAIM_SETTLED = 'SETTLED'
CLAIM_CANCELLED = 'CANCELLED'
CLAIM_ABANDONED = 'ABANDONED'

def calculate_payout(unit_face: int, fee_bps: int, decision: str) -> tuple[int, int]:
    if not 0 <= fee_bps <= 10000:
        raise ValueError('fee_bps must be between 0 and 10000')
    if unit_face < 0:
        raise ValueError('unit_face must be non-negative')
    if decision == DECISION_FULL:
        fee_amount = unit_face * fee_bps // 10000
        payout = unit_face - fee_amount
        return (payout, fee_amount)
    elif decision == DECISION_HALF:
        gross_half = unit_face // 2
        fee_amount = gross_half * fee_bps // 10000
        payout = gross_half - fee_amount
        return (payout, fee_amount)
    elif decision in (DECISION_NONE, DECISION_INCONCLUSIVE):
        return (0, 0)
    else:
        raise ValueError(f'Unknown decision: {decision}')

def verify_solvency_invariant(pool_balance: int, live_units: int, unit_face: int) -> bool:
    if pool_balance < 0 or live_units < 0 or unit_face < 0:
        return False
    return pool_balance >= live_units * unit_face

def max_withdrawable(pool_balance: int, live_units: int, unit_face: int) -> int:
    exposure = live_units * unit_face
    if pool_balance < exposure:
        return 0
    return pool_balance - exposure
MAX_URL_LENGTH = 512
MAX_URLS_COUNT = 5
MAX_FETCH_CHARS = 4000
ALLOWED_SCHEME = 'https'
ALLOWED_PORT = 443
BLOCKED_EXACT_HOSTS = {'localhost', 'metadata.google.internal', 'instance-data'}
BLOCKED_DOMAIN_SUFFIXES = ('.local', '.internal', '.arpa', '.home.arpa', '.localhost', '.lan', '.test', '.example', '.invalid')
HOSTNAME_REGEX = re.compile('^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\\.[A-Za-z]{2,63}$')

def validate_url(url: str) -> tuple[bool, str]:
    if not isinstance(url, str):
        return (False, 'URL must be a string')
    url = url.strip()
    if not url:
        return (False, 'URL cannot be empty')
    if len(url) > MAX_URL_LENGTH:
        return (False, f'URL exceeds maximum length of {MAX_URL_LENGTH}')
    if any((c <= ' ' or c in '\x7f' for c in url)):
        return (False, 'URL contains whitespace or control characters')
    try:
        parsed = urlparse(url)
    except Exception as e:
        return (False, f'URL parse failed: {str(e)}')
    if parsed.scheme.lower() != ALLOWED_SCHEME:
        return (False, f'Only {ALLOWED_SCHEME} is allowed')
    if parsed.username or parsed.password:
        return (False, 'Credentials in URL are strictly forbidden')
    if not parsed.hostname:
        return (False, 'URL missing host')
    host = parsed.hostname.lower().rstrip('.')
    port = parsed.port
    if port is not None and port != ALLOWED_PORT:
        return (False, f'Non-standard port {port} forbidden (only {ALLOWED_PORT} allowed)')
    if host in BLOCKED_EXACT_HOSTS:
        return (False, f'Host {host} is blocked')
    if any((host.endswith(suffix) for suffix in BLOCKED_DOMAIN_SUFFIXES)):
        return (False, f'Host domain suffix is blocked: {host}')
    if ':' in host or '[' in host or ']' in host:
        return (False, 'IPv6 literals are forbidden')
    is_numeric_ip = False
    parts = host.split('.')
    if all((p.isdigit() for p in parts)) and len(parts) in (1, 2, 3, 4):
        is_numeric_ip = True
    if is_numeric_ip:
        if len(parts) != 4:
            return (False, 'Only canonical 4-part decimal IPv4 addresses are permitted')
        for p in parts:
            if len(p) > 1 and p.startswith('0'):
                return (False, 'Leading zeros in IP octets (octal notation) forbidden')
            try:
                val = int(p)
                if val < 0 or val > 255:
                    return (False, 'IP octet out of range 0-255')
            except ValueError:
                return (False, 'Invalid decimal IP octet')
        try:
            ip_obj = ipaddress.IPv4Address(host)
        except Exception:
            return (False, 'Invalid IPv4 address')
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
            return (False, f'IP address {host} belongs to a restricted/private network')
        cgnat = ipaddress.IPv4Network('100.64.0.0/10')
        if ip_obj in cgnat:
            return (False, f'IP address {host} belongs to CGNAT (100.64.0.0/10)')
        if ip_obj in ipaddress.IPv4Network('0.0.0.0/8'):
            return (False, f'IP address {host} is invalid (0.0.0.0/8)')
    elif not HOSTNAME_REGEX.match(host):
        return (False, f"Hostname '{host}' is invalid or does not have a valid alphabetic TLD")
    path = parsed.path if parsed.path else '/'
    query_str = f'?{parsed.query}' if parsed.query else ''
    canonical_url = f'https://{host}{path}{query_str}'
    return (True, canonical_url)

def validate_urls_list(urls: list[str]) -> tuple[bool, list[str], str]:
    if not isinstance(urls, list):
        return (False, [], 'URLs must be a list')
    if len(urls) == 0:
        return (False, [], 'At least one evidence URL is required')
    if len(urls) > MAX_URLS_COUNT:
        return (False, [], f'Exceeded maximum number of URLs ({MAX_URLS_COUNT})')
    canonical_urls = []
    seen = set()
    for u in urls:
        ok, res = validate_url(u)
        if not ok:
            return (False, [], f"Invalid URL '{u}': {res}")
        if res in seen:
            return (False, [], f'Duplicate URL detected: {res}')
        seen.add(res)
        canonical_urls.append(res)
    return (True, canonical_urls, '')
MAX_NARRATIVE_LENGTH = 1000
MAX_POLICY_LENGTH = 8000
FORBIDDEN_PATTERNS = [re.compile('`{3,}'), re.compile('\\[{2,}'), re.compile('\\]{2,}'), re.compile('<{3,}'), re.compile('>{3,}')]

def sanitize_text(text: str, max_length: int) -> str:
    if not isinstance(text, str):
        return ''
    clean = re.sub('[\\r\\n\\t]+', ' ', text)
    clean = re.sub('[^\\x20-\\x7E]', ' ', clean)
    for pat in FORBIDDEN_PATTERNS:
        clean = pat.sub(' ', clean)
    clean = re.sub('\\s+', ' ', clean).strip()
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip()
    return clean

def compute_policy_hash(policy_text: str) -> str:
    sanitized = sanitize_text(policy_text, MAX_POLICY_LENGTH)
    return hashlib.sha256(sanitized.encode('utf-8')).hexdigest()

def force_consistency(raw_decision: str, clause_ids: list[str], exclusion_ids: list[str], evidence_usable: list[int], code: str) -> dict:
    decision = str(raw_decision).strip().upper()
    if decision not in VALID_DECISIONS:
        decision = DECISION_INCONCLUSIVE
    clean_clauses = sorted(list({str(c).strip() for c in clause_ids if str(c).strip()}))
    clean_exclusions = sorted(list({str(e).strip() for e in exclusion_ids if str(e).strip()}))
    clean_usable = []
    for u in evidence_usable:
        try:
            val = int(u)
            if val >= 0 and val not in clean_usable:
                clean_usable.append(val)
        except (ValueError, TypeError):
            continue
    clean_usable.sort()
    clean_code = str(code).strip() if code else 'OK'
    if not clean_usable:
        decision = DECISION_INCONCLUSIVE
        clean_code = 'NO_USABLE_EVIDENCE'
    if decision in (DECISION_FULL, DECISION_HALF) and clean_exclusions:
        decision = DECISION_NONE
        clean_code = 'VOIDED_BY_EXCLUSIONS'
    if decision in (DECISION_FULL, DECISION_HALF) and (not clean_clauses):
        decision = DECISION_NONE
        clean_code = 'NO_CLAUSE_BREACHED'
    return {'clause_ids': clean_clauses, 'code': clean_code, 'decision': decision, 'evidence_usable': clean_usable, 'exclusion_ids': clean_exclusions}

def parse_llm_judgment_response(raw_response: str) -> dict:
    if not raw_response or not isinstance(raw_response, str):
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], 'EMPTY_RESPONSE')
    json_match = re.search('\\{[\\s\\S]*\\}', raw_response)
    if not json_match:
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], 'NO_JSON_FOUND')
    try:
        data = json.loads(json_match.group(0))
    except Exception:
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], 'JSON_PARSE_ERROR')
    raw_decision = data.get('decision', DECISION_INCONCLUSIVE)
    clause_ids = data.get('clause_ids', [])
    if not isinstance(clause_ids, list):
        clause_ids = []
    exclusion_ids = data.get('exclusion_ids', [])
    if not isinstance(exclusion_ids, list):
        exclusion_ids = []
    evidence_usable = data.get('evidence_usable', [])
    if not isinstance(evidence_usable, list):
        evidence_usable = []
    code = data.get('code', 'OK')
    return force_consistency(raw_decision, clause_ids, exclusion_ids, evidence_usable, code)

def canonicalize_for_comparison(judgment_dict: dict) -> str:
    comparable = {'clause_ids': sorted(list(judgment_dict.get('clause_ids', []))), 'code': str(judgment_dict.get('code', '')), 'decision': str(judgment_dict.get('decision', DECISION_INCONCLUSIVE)), 'evidence_usable': sorted(list(judgment_dict.get('evidence_usable', []))), 'exclusion_ids': sorted(list(judgment_dict.get('exclusion_ids', [])))}
    return json.dumps(comparable, sort_keys=True, separators=(',', ':'))

def build_adjudication_prompt(policy_text: str, narrative: str, evidence_items: list[dict]) -> str:
    lines = ['You are an impartial coverage bond arbitrator evaluating an incident claim under a strict policy.', 'Your task is to review the policy, the incident narrative, and the independently retrieved HTTPS evidence.', '', 'AVAILABLE DECISION OUTCOMES (choose EXACTLY one):', '- FULL: The evidence conclusively proves a total outage/breach under the policy terms.', '- HALF: The evidence conclusively proves a partial outage/breach under the policy terms.', '- NONE: The incident did not breach policy terms, or an explicit exclusion applies.', '- INCONCLUSIVE: The evidence is insufficient, contradictory, unreachable, or unverified.', '', 'FROZEN POLICY TERMS:', f'[[POLICY_START]]\n{policy_text}\n[[POLICY_END]]', '', 'CLAIMANT NARRATIVE:', f'[[NARRATIVE_START]]\n{narrative}\n[[NARRATIVE_END]]', '', 'EVIDENCE RETRIEVED FROM HTTPS URLS:']
    for item in evidence_items:
        idx = item.get('index', 0)
        url = item.get('url', '')
        content = item.get('content', '')
        lines.append(f'Evidence #{idx} from {url}:')
        lines.append(f'[[EVIDENCE_{idx}_START]]\n{content}\n[[EVIDENCE_{idx}_END]]')
    lines.extend(['', 'OUTPUT REQUIREMENT:', 'Return ONLY a valid JSON object with EXACTLY this structure:', '{', '  "decision": "FULL" | "HALF" | "NONE" | "INCONCLUSIVE",', '  "clause_ids": ["CLAUSE-1", ...],', '  "exclusion_ids": ["EXCLUSION-1", ...],', '  "evidence_usable": [0, 1, ...],', '  "code": "REASON_CODE_IN_CAPS"', '}', 'Do not include any conversational preamble or markdown backticks.'])
    return '\n'.join(lines)
MAX_JUDGE_ATTEMPTS = 3
EXPIRY_WINDOW_SECONDS = 259200

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())

def _sender() -> str:
    return str(gl.message.sender_address)

def _sender_hex() -> str:
    return Address(_sender()).as_hex.lower()

def _make_unit_id(n: int) -> str:
    return 'SOL-U' + str(n).zfill(8)

def _make_claim_id(n: int) -> str:
    return 'SOL-C' + str(n).zfill(8)

@gl.evm.contract_interface
class _Recipient:

    class View:
        pass

    class Write:
        pass

class Solvent(gl.contract.Contract):
    issuer: str
    treasury: str
    policy_text: str
    policy_hash: str
    unit_face: u256
    max_units: u256
    claim_bond: u256
    fee_bps: u256
    pool_balance: u256
    live_units: u256
    unit_counter: u256
    claim_counter: u256
    units: TreeMap[str, str]
    claims: TreeMap[str, str]
    claimable: TreeMap[str, u256]

    def __init__(self, treasury: str, policy_text: str, unit_face: str, max_units: str, claim_bond: str, fee_bps: str):
        clean_policy = sanitize_text(policy_text, MAX_POLICY_LENGTH)
        if not clean_policy:
            raise gl.vm.UserError('POLICY_EMPTY')
        try:
            face = int(str(unit_face))
            mu = int(str(max_units))
            cb = int(str(claim_bond))
            fb = int(str(fee_bps))
            treasury_hex = Address(treasury).as_hex.lower()
        except Exception:
            raise gl.vm.UserError('BAD_ARGUMENT')
        if face <= 0:
            raise gl.vm.UserError('BAD_UNIT_FACE')
        if mu <= 0:
            raise gl.vm.UserError('BAD_MAX_UNITS')
        if cb < 0:
            raise gl.vm.UserError('BAD_CLAIM_BOND')
        if fb < 0 or fb > 10000:
            raise gl.vm.UserError('BAD_FEE_BPS')
        self.issuer = _sender_hex()
        self.treasury = treasury_hex
        self.policy_text = clean_policy
        self.policy_hash = compute_policy_hash(clean_policy)
        self.unit_face = u256(face)
        self.max_units = u256(mu)
        self.claim_bond = u256(cb)
        self.fee_bps = u256(fb)
        self.pool_balance = u256(0)
        self.live_units = u256(0)
        self.unit_counter = u256(0)
        self.claim_counter = u256(0)

    def _load_unit(self, unit_id: str) -> dict:
        raw = self.units.get(unit_id)
        if raw is None:
            raise gl.vm.UserError('UNIT_NOT_FOUND')
        return json.loads(raw)

    def _save_unit(self, unit_id: str, rec: dict) -> None:
        self.units[unit_id] = json.dumps(rec)

    def _load_claim(self, claim_id: str) -> dict:
        raw = self.claims.get(claim_id)
        if raw is None:
            raise gl.vm.UserError('CLAIM_NOT_FOUND')
        return json.loads(raw)

    def _save_claim(self, claim_id: str, rec: dict) -> None:
        self.claims[claim_id] = json.dumps(rec)

    def _credit(self, addr: str, amount: int) -> None:
        if not addr or amount <= 0:
            return
        key = addr.lower()
        cur = int(self.claimable.get(key, u256(0)))
        self.claimable[key] = u256(cur + amount)

    def _owed(self, addr: str) -> int:
        return int(self.claimable.get(addr.lower(), u256(0)))

    def _assert_solvent(self) -> None:
        if not verify_solvency_invariant(int(self.pool_balance), int(self.live_units), int(self.unit_face)):
            raise gl.vm.UserError('SOLVENCY_INVARIANT_BROKEN')

    @gl.public.write.payable
    def top_up_pool(self) -> str:
        deposit = int(gl.message.value)
        if deposit <= 0:
            raise gl.vm.UserError('NO_DEPOSIT')
        self.pool_balance = u256(int(self.pool_balance) + deposit)
        self._assert_solvent()
        return str(int(self.pool_balance))

    @gl.public.write
    def enroll_unit(self) -> str:
        if int(self.unit_counter) >= int(self.max_units):
            raise gl.vm.UserError('MAX_UNITS_REACHED')
        new_live = int(self.live_units) + 1
        if not verify_solvency_invariant(int(self.pool_balance), new_live, int(self.unit_face)):
            raise gl.vm.UserError('POOL_INSOLVENT_FOR_NEW_UNIT')
        n = int(self.unit_counter) + 1
        self.unit_counter = u256(n)
        self.live_units = u256(new_live)
        unit_id = _make_unit_id(n)
        self._save_unit(unit_id, {'unit_id': unit_id, 'beneficiary': _sender_hex(), 'policy_hash': self.policy_hash, 'status': UNIT_ACTIVE, 'open_claim_id': '', 'claims_count': 0, 'enrolled_at': _now_ts()})
        return unit_id

    @gl.public.write.payable
    def file_claim(self, unit_id: str, narrative: str, urls: list) -> str:
        bond = int(gl.message.value)
        if bond < int(self.claim_bond):
            raise gl.vm.UserError('BOND_TOO_SMALL')
        unit = self._load_unit(unit_id)
        if unit['status'] != UNIT_ACTIVE:
            raise gl.vm.UserError('UNIT_NOT_ACTIVE')
        if unit['beneficiary'] != _sender_hex():
            raise gl.vm.UserError('NOT_BENEFICIARY')
        if unit['open_claim_id']:
            raise gl.vm.UserError('UNIT_HAS_OPEN_CLAIM')
        clean_narrative = sanitize_text(narrative, MAX_NARRATIVE_LENGTH)
        if not clean_narrative:
            raise gl.vm.UserError('NARRATIVE_EMPTY')
        ok, canonical_urls, reason = validate_urls_list(urls)
        if not ok:
            raise gl.vm.UserError('BAD_EVIDENCE_URLS:' + reason)
        n = int(self.claim_counter) + 1
        self.claim_counter = u256(n)
        claim_id = _make_claim_id(n)
        self._save_claim(claim_id, {'claim_id': claim_id, 'unit_id': unit_id, 'beneficiary': unit['beneficiary'], 'narrative': clean_narrative, 'urls': canonical_urls, 'bond': bond, 'status': CLAIM_OPEN, 'decision': '', 'judge_attempts': 0, 'filed_at': _now_ts(), 'comparable': {}})
        unit['open_claim_id'] = claim_id
        unit['claims_count'] = int(unit.get('claims_count', 0)) + 1
        self._save_unit(unit_id, unit)
        return claim_id

    @gl.public.write
    def adjudicate(self, claim_id: str) -> str:
        rec = self._load_claim(claim_id)
        if rec['status'] != CLAIM_OPEN:
            raise gl.vm.UserError('CLAIM_NOT_OPEN')
        if int(rec.get('judge_attempts', 0)) >= MAX_JUDGE_ATTEMPTS:
            raise gl.vm.UserError('MAX_ATTEMPTS_REACHED')
        urls = list(rec['urls'])
        narrative = rec['narrative']
        policy_text = self.policy_text

        def leader_fn() -> str:
            items = []
            for idx, u in enumerate(urls):
                ok, _canonical = validate_url(u)
                if not ok:
                    content = '[BLOCKED_BY_SSRF_VALIDATOR]'
                else:
                    try:
                        page = gl.nondet.web.get(u)
                        body = getattr(page, 'body', None)
                        if body is None:
                            body = str(page)
                        clean = sanitize_text(body, MAX_FETCH_CHARS)
                        content = clean if clean else '[EMPTY_RESPONSE]'
                    except Exception:
                        content = '[FETCH_ERROR]'
                items.append({'index': idx, 'url': u, 'content': content})
            prompt = build_adjudication_prompt(policy_text, narrative, items)
            try:
                raw = gl.nondet.exec_prompt(prompt)
            except Exception:
                raw = ''
            parsed = parse_llm_judgment_response(raw)
            return canonicalize_for_comparison(parsed)

        def validator_fn(leader_result) -> bool:
            payload = getattr(leader_result, 'calldata', None)
            if payload is None:
                return False
            try:
                leader_str = str(payload)
            except Exception:
                return False
            if not leader_str:
                return False
            mine = leader_fn()
            return leader_str == mine
        agreed_raw = gl.vm.run_nondet(leader_fn, validator_fn)
        try:
            agreed = json.loads(str(agreed_raw))
        except Exception:
            agreed = {}
        if not isinstance(agreed, dict):
            agreed = {}
        decision = str(agreed.get('decision', DECISION_INCONCLUSIVE))
        if decision not in VALID_DECISIONS:
            decision = DECISION_INCONCLUSIVE
        rec = self._load_claim(claim_id)
        rec['judge_attempts'] = int(rec.get('judge_attempts', 0)) + 1
        rec['decision'] = decision
        rec['comparable'] = agreed
        unit = self._load_unit(rec['unit_id'])
        face = int(self.unit_face)
        bene = rec['beneficiary']
        bond = int(rec['bond'])
        if decision == DECISION_FULL or decision == DECISION_HALF:
            payout, fee = calculate_payout(face, int(self.fee_bps), decision)
            self._credit(bene, payout + bond)
            if fee > 0:
                self._credit(self.treasury, fee)
            lost = face if decision == DECISION_FULL else face // 2
            self.pool_balance = u256(int(self.pool_balance) - lost)
            self.live_units = u256(int(self.live_units) - 1)
            unit['status'] = UNIT_CLAIMED_FULL if decision == DECISION_FULL else UNIT_CLAIMED_HALF
            unit['open_claim_id'] = ''
            rec['status'] = CLAIM_APPROVED
        elif decision == DECISION_NONE:
            if bond > 0:
                self._credit(self.treasury, bond)
            unit['open_claim_id'] = ''
            rec['status'] = CLAIM_DENIED
        else:
            if bond > 0:
                self._credit(bene, bond)
            unit['open_claim_id'] = ''
            rec['status'] = CLAIM_INCONCLUSIVE
        self._save_claim(claim_id, rec)
        self._save_unit(unit['unit_id'], unit)
        self._assert_solvent()
        return decision

    @gl.public.write
    def cancel_stale_claim(self, claim_id: str) -> str:
        rec = self._load_claim(claim_id)
        if rec['status'] != CLAIM_OPEN:
            raise gl.vm.UserError('CLAIM_NOT_OPEN')
        attempts = int(rec.get('judge_attempts', 0))
        elapsed = _now_ts() - int(rec.get('filed_at', 0))
        if attempts < MAX_JUDGE_ATTEMPTS and elapsed < EXPIRY_WINDOW_SECONDS:
            raise gl.vm.UserError('NOT_YET_CANCELLABLE')
        bond = int(rec['bond'])
        if bond > 0:
            self._credit(rec['beneficiary'], bond)
        rec['status'] = CLAIM_CANCELLED
        self._save_claim(claim_id, rec)
        unit = self._load_unit(rec['unit_id'])
        unit['open_claim_id'] = ''
        self._save_unit(unit['unit_id'], unit)
        return CLAIM_CANCELLED

    @gl.public.write
    def abandon_approved(self, claim_id: str) -> str:
        rec = self._load_claim(claim_id)
        if rec['status'] != CLAIM_APPROVED:
            raise gl.vm.UserError('CLAIM_NOT_APPROVED')
        caller = _sender_hex()
        if caller != rec['beneficiary'] and caller != self.issuer:
            raise gl.vm.UserError('NOT_AUTHORIZED')
        rec['status'] = CLAIM_ABANDONED
        self._save_claim(claim_id, rec)
        return CLAIM_ABANDONED

    @gl.public.write
    def expire_unit(self, unit_id: str) -> str:
        unit = self._load_unit(unit_id)
        if unit['status'] != UNIT_ACTIVE:
            raise gl.vm.UserError('UNIT_NOT_ACTIVE')
        if unit['open_claim_id']:
            raise gl.vm.UserError('UNIT_HAS_OPEN_CLAIM')
        unit['status'] = UNIT_EXPIRED
        self.live_units = u256(int(self.live_units) - 1)
        self._save_unit(unit_id, unit)
        self._assert_solvent()
        return UNIT_EXPIRED

    @gl.public.write
    def withdraw_pool(self, amount: str) -> str:
        if _sender_hex() != self.issuer:
            raise gl.vm.UserError('NOT_ISSUER')
        amt = int(str(amount))
        if amt <= 0:
            raise gl.vm.UserError('BAD_AMOUNT')
        available = max_withdrawable(int(self.pool_balance), int(self.live_units), int(self.unit_face))
        if amt > available:
            raise gl.vm.UserError('EXCEEDS_POOL_FLOOR')
        self.pool_balance = u256(int(self.pool_balance) - amt)
        self._credit(self.issuer, amt)
        self._assert_solvent()
        return str(amt)

    @gl.public.write
    def claim(self) -> str:
        key = _sender_hex()
        owed = self._owed(key)
        if owed <= 0:
            raise gl.vm.UserError('NOTHING_TO_CLAIM')
        self.claimable[key] = u256(0)
        _Recipient(gl.message.sender_address).emit_transfer(value=u256(owed))
        return str(owed)

    @gl.public.view
    def get_config(self) -> str:
        return json.dumps({'issuer': self.issuer, 'treasury': self.treasury, 'policy_hash': self.policy_hash, 'unit_face': str(int(self.unit_face)), 'max_units': str(int(self.max_units)), 'claim_bond': str(int(self.claim_bond)), 'fee_bps': int(self.fee_bps), 'max_judge_attempts': MAX_JUDGE_ATTEMPTS, 'expiry_window_seconds': EXPIRY_WINDOW_SECONDS, 'pool_balance': str(int(self.pool_balance)), 'live_units': str(int(self.live_units)), 'unit_count': str(int(self.unit_counter)), 'claim_count': str(int(self.claim_counter)), 'decisions': list(VALID_DECISIONS)})

    @gl.public.view
    def get_policy(self) -> str:
        return json.dumps({'policy_text': self.policy_text, 'policy_hash': self.policy_hash})

    @gl.public.view
    def get_solvency(self) -> str:
        pool = int(self.pool_balance)
        live = int(self.live_units)
        face = int(self.unit_face)
        return json.dumps({'pool_balance': str(pool), 'exposure': str(live * face), 'live_units': str(live), 'unit_face': str(face), 'is_solvent': verify_solvency_invariant(pool, live, face), 'withdrawable': str(max_withdrawable(pool, live, face))})

    @gl.public.view
    def get_unit(self, unit_id: str) -> str:
        return json.dumps(self._load_unit(unit_id))

    @gl.public.view
    def get_claim(self, claim_id: str) -> str:
        return json.dumps(self._load_claim(claim_id))

    @gl.public.view
    def get_claimable(self, address: str) -> str:
        return str(self._owed(Address(address).as_hex))

    @gl.public.view
    def get_board(self) -> str:
        ucount = int(self.unit_counter)
        ustart = max(1, ucount - 49)
        units = []
        for i in range(ustart, ucount + 1):
            raw = self.units.get(_make_unit_id(i))
            if raw is not None:
                units.append(json.loads(raw))
        ccount = int(self.claim_counter)
        cstart = max(1, ccount - 49)
        claims = []
        for i in range(cstart, ccount + 1):
            raw = self.claims.get(_make_claim_id(i))
            if raw is not None:
                claims.append(json.loads(raw))
        return json.dumps({'units': units, 'claims': claims, 'unit_count': str(ucount), 'claim_count': str(ccount)})
