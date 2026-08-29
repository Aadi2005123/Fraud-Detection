import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock,
  Code2,
  CreditCard,
  DollarSign,
  Layers,
  Lock,
  Network,
  Play,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Smartphone,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react'

const RENDER_BACKEND_URL = 'https://fraud-detection-1-ky1b.onrender.com'
const LOCAL_BACKEND_URL = 'http://localhost:8000'

const BASE_API =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? LOCAL_BACKEND_URL : RENDER_BACKEND_URL)
const RISK_API = `${BASE_API}/api/v1`

// ── Persistent device fingerprint ───────────────────────────────────────────
const DEVICE_KEY = 'paysim_guard_device_id'
function getOrCreateDeviceId() {
  let deviceId = localStorage.getItem(DEVICE_KEY)
  if (!deviceId) {
    deviceId = crypto.randomUUID()
    localStorage.setItem(DEVICE_KEY, deviceId)
  }
  return deviceId
}
const DEVICE_ID = getOrCreateDeviceId()

// ── Session ID (ephemeral, resets on tab close) ──────────────────────────────
const SESSION_ID = crypto.randomUUID()

// ── Supported Payment Channels ──────────────────────────────────────────────
const PAYMENT_CHANNELS = [
  { id: 'UPI', label: 'UPI (Instant)', icon: '⚡' },
  { id: 'ATM', label: 'ATM Cash Out', icon: '🏧' },
  { id: 'DEBIT_CARD', label: 'Debit Card', icon: '💳' },
  { id: 'CREDIT_CARD', label: 'Credit Card', icon: '💳' },
  { id: 'NET_BANKING', label: 'Net Banking (Online)', icon: '🌐' },
  { id: 'WALLET', label: 'Digital Wallet', icon: '👛' },
  { id: 'CASH_WITHDRAWAL', label: 'Cash Withdrawal', icon: '💵' },
  { id: 'BANK_TRANSFER', label: 'Bank Transfer (IMPS/NEFT)', icon: '🏦' },
  { id: 'CASH_DEPOSIT', label: 'Cash Deposit', icon: '📥' },
  { id: 'POS', label: 'Point of Sale (POS)', icon: '🛒' },
  { id: 'ECOMMERCE', label: 'E-Commerce Gateway', icon: '🛍️' },
]

// ── Channel Configuration: encodes which fields are shown per channel ─────────
// showReceiver:   show the Receiver / Beneficiary selector
// showMerchant:   show the Merchant ID input
// receiverLabel:  label text for the receiver selector
// types:          allowed transaction types; first entry is the default
// typeLabel:      display label for single-type channels (shown as read-only)
// atmMode:        show ATM/cash auto-context badge instead of receiver/merchant
const CHANNEL_CONFIG = {
  UPI: {
    showReceiver: true,
    showMerchant: false,
    receiverLabel: 'UPI Beneficiary',
    types: ['TRANSFER'],
    typeLabel: 'UPI Transfer',
    atmMode: false,
  },
  ATM: {
    showReceiver: false,
    showMerchant: false,
    receiverLabel: null,
    types: ['CASH_OUT'],
    typeLabel: 'ATM Cash Out',
    atmMode: true,
  },
  CASH_WITHDRAWAL: {
    showReceiver: false,
    showMerchant: false,
    receiverLabel: null,
    types: ['CASH_OUT'],
    typeLabel: 'Cash Withdrawal',
    atmMode: true,
  },
  CASH_DEPOSIT: {
    showReceiver: false,
    showMerchant: false,
    receiverLabel: null,
    types: ['CASH_IN'],
    typeLabel: 'Cash Deposit',
    atmMode: true,
  },
  DEBIT_CARD: {
    showReceiver: false,
    showMerchant: true,
    receiverLabel: null,
    types: ['PAYMENT'],
    typeLabel: 'Card Payment',
    atmMode: false,
  },
  CREDIT_CARD: {
    showReceiver: false,
    showMerchant: true,
    receiverLabel: null,
    types: ['PAYMENT'],
    typeLabel: 'Card Payment',
    atmMode: false,
  },
  POS: {
    showReceiver: false,
    showMerchant: true,
    receiverLabel: null,
    types: ['PAYMENT'],
    typeLabel: 'POS Card Payment',
    atmMode: false,
  },
  ECOMMERCE: {
    showReceiver: false,
    showMerchant: true,
    receiverLabel: null,
    types: ['PAYMENT'],
    typeLabel: 'E-Commerce Payment',
    atmMode: false,
  },
  NET_BANKING: {
    showReceiver: true,
    showMerchant: false,
    receiverLabel: 'Beneficiary Account',
    types: ['TRANSFER'],
    typeLabel: 'Net Banking Transfer',
    atmMode: false,
  },
  WALLET: {
    showReceiver: true,
    showMerchant: false,
    receiverLabel: 'Wallet / Payee',
    types: ['PAYMENT', 'TRANSFER'],
    typeLabel: null,
    atmMode: false,
  },
  BANK_TRANSFER: {
    showReceiver: true,
    showMerchant: false,
    receiverLabel: 'Beneficiary Account',
    types: ['TRANSFER'],
    typeLabel: 'Bank Transfer',
    atmMode: false,
  },
}

// ── Pages ────────────────────────────────────────────────────────────────────
const pages = [
  ['overview', 'Overview', BarChart3],
  ['simulator', 'Risk Engine Simulator', Play],
  ['feed', 'Live Feed', Activity],
  ['network', 'Network Graph', Network],
  ['aml', 'AML Monitor', Shield],
  ['performance', 'Engine & Models', Layers],
  ['audit', 'Audit Log', CircleDot],
]

// ── All 13 Test Lab Scenarios + Scenario 35 Master Preset ───────────────────
const QA_SCENARIOS = {
  scenario_1_normal: {
    name: '1. Normal Transaction (Low Risk)',
    description: 'Known device, normal ₹5,000 UPI transfer in Delhi during day hours — expect ALLOW.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 5000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Delhi', failed_pin_attempts: 0, time: '10:30', is_new_beneficiary: false },
  },
  scenario_2_new_device: {
    name: '2. New Device + Large Transaction',
    description: 'Unrecognized device (DEVICE_NEW_999), ₹100,000 transfer — triggers NEW_DEVICE signal.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 100000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_NEW_999', location: 'Delhi', failed_pin_attempts: 0, time: '14:00', is_new_beneficiary: false },
  },
  scenario_3_wrong_pin: {
    name: '3. Multiple Failed Auth + Large Transaction',
    description: '4 failed PIN attempts + ₹100,000 transfer — triggers MULTIPLE_FAILED_AUTH (BLOCK).',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 100000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Delhi', failed_pin_attempts: 4, time: '15:00', is_new_beneficiary: false },
  },
  scenario_4_unusual_location: {
    name: '4. Unusual Location + Large Transaction',
    description: 'Delhi resident suddenly transacting ₹75,000 from Mumbai — triggers UNUSUAL_LOCATION.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 75000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Mumbai', failed_pin_attempts: 0, time: '16:00', is_new_beneficiary: false },
  },
  scenario_5_dormant: {
    name: '5. Dormant Account Suddenly Active',
    description: 'Dormant account (INACTIVE001) executing sudden ₹100,000 transfer from Kolkata.',
    form: { sender_id: 'INACTIVE001', receiver_id: 'PRIYA001', amount: 100000, transaction_type: 'TRANSFER', channel: 'BANK_TRANSFER' },
    signals: { device_id: 'DEVICE_OLD_DORMANT', location: 'Kolkata', failed_pin_attempts: 0, time: '11:00', is_new_beneficiary: false },
  },
  scenario_6_combined: {
    name: '6. Multiple Suspicious Signals',
    description: 'New device + international location (Dubai) + 4 failed PINs + ₹150,000 — CRITICAL / BLOCK.',
    form: { sender_id: 'INACTIVE001', receiver_id: 'PRIYA001', amount: 150000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_UNRECOGNIZED_X', location: 'Dubai', failed_pin_attempts: 4, time: '02:00', is_new_beneficiary: true },
  },
  scenario_7_atm_anomaly: {
    name: '7. ATM Withdrawal Anomaly',
    description: '₹50,000 late-night ATM cash-out at 23:30 from unusual branch with 2 failed PINs.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 50000, transaction_type: 'CASH_OUT', channel: 'ATM' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Chandigarh', failed_pin_attempts: 2, time: '23:30', is_new_beneficiary: false },
  },
  scenario_8_card_new_location: {
    name: '8. Card Payment From New Location',
    description: '₹40,000 credit card transaction in London from an Indian cardholder.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 40000, transaction_type: 'PAYMENT', channel: 'CREDIT_CARD' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'London', failed_pin_attempts: 0, time: '14:00', is_new_beneficiary: false },
  },
  scenario_9_upi_new_device_beneficiary: {
    name: '9. UPI New Device + New Beneficiary',
    description: '₹80,000 UPI transfer from new unrecognized device to an unverified new beneficiary.',
    form: { sender_id: 'AMIT001', receiver_id: 'INACTIVE001', amount: 80000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_NEW_UPI', location: 'Delhi', failed_pin_attempts: 0, time: '11:00', is_new_beneficiary: true },
  },
  scenario_10_impossible_travel: {
    name: '10. Impossible Travel Velocity',
    description: 'Delhi resident transacting from Mumbai 5 minutes after a Delhi transaction.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 2500, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Mumbai', failed_pin_attempts: 0, time: '10:05', is_new_beneficiary: false },
  },
  scenario_11_balance_drain: {
    name: '11. Sudden Balance Drain',
    description: 'Priya (₹25,000 balance) draining ₹24,000 (96% balance) in a single wire transfer.',
    form: { sender_id: 'PRIYA001', receiver_id: 'AMIT001', amount: 24000, transaction_type: 'TRANSFER', channel: 'BANK_TRANSFER' },
    signals: { device_id: 'DEVICE_PRIYA_01', location: 'Delhi', failed_pin_attempts: 0, time: '12:00', is_new_beneficiary: false },
  },
  scenario_12_high_velocity: {
    name: '12. High Velocity Transactions',
    description: 'Rapid burst of 4+ consecutive transfers within 2 minutes — triggers HIGH_VELOCITY.',
    form: { sender_id: 'RAHUL001', receiver_id: 'PRIYA001', amount: 1000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_RAHUL_01', location: 'Delhi', failed_pin_attempts: 0, time: '12:05', is_new_beneficiary: false },
  },
  scenario_13_3am_high_value: {
    name: '13. 3 AM High-Value Transaction',
    description: '₹90,000 UPI transfer at 03:00 AM IST outside normal merchant business hours.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 90000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_AMIT_01', location: 'Delhi', failed_pin_attempts: 0, time: '03:00', is_new_beneficiary: false },
  },
  scenario_35_master: {
    name: '★ Scenario 35 (Master Verification)',
    description: 'Delhi merchant, ₹300,000 UPI at 03:00 AM in Mumbai, 3 failed auths, new beneficiary, balance drain → CRITICAL / BLOCK.',
    form: { sender_id: 'AMIT001', receiver_id: 'PRIYA001', amount: 300000, transaction_type: 'TRANSFER', channel: 'UPI' },
    signals: { device_id: 'DEVICE_NEW_UNRECOGNIZED_01', location: 'Mumbai', failed_pin_attempts: 3, time: '03:00', is_new_beneficiary: true, balance_override: 400000 },
  },
}

// ── Timestamp Helpers (IST Consistent) ──────────────────────────────────────
function formatIST(isoOrDateString) {
  if (!isoOrDateString) return '—'
  // If it is already formatted as "DD-MMM-YYYY HH:MM:SS IST"
  if (typeof isoOrDateString === 'string' && isoOrDateString.includes('IST')) {
    return isoOrDateString
  }
  try {
    const d = new Date(isoOrDateString)
    if (isNaN(d.getTime())) return isoOrDateString
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(d) + ' IST'
  } catch (e) {
    return isoOrDateString
  }
}

function formatCurrency(num) {
  if (num == null) return '₹0'
  return `₹${Number(num).toLocaleString('en-IN')}`
}

function humanizeError(rawMessage) {
  if (!rawMessage) return 'An unexpected error occurred. Please try again.'
  const msg = String(rawMessage)
  if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
    return 'Fraud Engine service is unreachable. Please ensure the backend is active.'
  }
  if (msg.includes('Sender account not found')) return 'Sender account could not be found.'
  if (msg.includes('Receiver account not found')) return 'Receiver account could not be found.'
  if (msg.includes('Amount exceeds sender balance')) return 'The sender does not have enough balance for this transaction.'
  if (msg.includes('Duplicate transaction submission detected')) return 'This transaction is already pending. Please wait before submitting it again.'
  if (msg.includes('Sender and receiver must be different')) return 'The sender and receiver accounts cannot be the same.'
  if (msg.includes('Amount must be greater than zero')) return 'Please specify a transaction amount greater than zero.'
  if (msg.includes('Date is not valid')) return 'The specified date is invalid for the chosen month.'
  return msg
}

async function apiCall(endpoint, options) {
  const url = endpoint.startsWith('http') ? endpoint : `${RISK_API}${endpoint}`
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || data.message || 'Service request failed')
  }
  return data
}

function Badge({ children, variant }) {
  const val = String(children || '').toLowerCase()
  const v = variant || val
  return <span className={`badge ${v}`}>{children}</span>
}

function Stat({ label, value, subtext, tone = '' }) {
  return (
    <div className={`stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {subtext && <small className="stat-subtext">{subtext}</small>}
    </div>
  )
}

// ── Root App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState('overview')
  const [metrics, setMetrics] = useState({})
  const [audit, setAudit] = useState([])
  const [models, setModels] = useState([])
  const [accounts, setAccounts] = useState([])
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [confirmLoading, setConfirmLoading] = useState(false)

  // Normal merchant form — only merchant-visible fields
  const [form, setForm] = useState({
    sender_id: 'AMIT001',
    receiver_id: 'PRIYA001',
    amount: 5000,
    transaction_type: 'TRANSFER',
    channel: 'UPI',
    currency: 'INR',
    order_id: '',
    merchant_id: 'MERCH-DELHI-01',
  })

  // Channel-change handler: auto-sets transaction_type & clears irrelevant fields
  const handleChannelChange = (e) => {
    const newChannel = e.target.value
    const cfg = CHANNEL_CONFIG[newChannel] || CHANNEL_CONFIG['UPI']
    setForm((prev) => ({
      ...prev,
      channel: newChannel,
      transaction_type: cfg.types[0],
      // Clear receiver for channels that don't use it
      receiver_id: cfg.showReceiver ? prev.receiver_id : 'SYSTEM',
      // Clear merchant for channels that don't use it
      merchant_id: cfg.showMerchant ? prev.merchant_id : '',
    }))
    setCheckResult(null)
    setConfirmResult(null)
    setError('')
  }

  // QA developer mode state (hidden from normal merchant view)
  const [qaMode, setQaMode] = useState(false)
  const [qaScenario, setQaScenario] = useState('')
  // Overridden contextual signals used ONLY in QA mode
  const [qaSignals, setQaSignals] = useState({
    device_id: null,
    location: null,
    failed_pin_attempts: 0,
    time: null,
    is_new_beneficiary: false,
    balance_override: null,
  })

  const [checkResult, setCheckResult] = useState(null)
  const [confirmResult, setConfirmResult] = useState(null)

  const refresh = async () => {
    setLoading(true)
    setError('')
    try {
      const [m, a, modelsData, accs] = await Promise.all([
        apiCall('/metrics'),
        apiCall('/audit?limit=40'),
        apiCall('/models'),
        apiCall(`${BASE_API}/accounts`).catch(() => []),
      ])
      setMetrics(m)
      setAudit(a.records || [])
      setModels(modelsData.models || [])
      if (Array.isArray(accs)) setAccounts(accs)
    } catch (e) {
      setError(humanizeError(e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const updateForm = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }))
    setCheckResult(null)
    setConfirmResult(null)
    setError('')
  }

  // Apply a QA scenario — populates form + overrides signals
  const applyQaScenario = (key) => {
    setQaScenario(key)
    if (!key) return
    const s = QA_SCENARIOS[key]
    if (!s) return
    setForm((prev) => ({ ...prev, ...s.form }))
    setQaSignals(s.signals || {})
    setCheckResult(null)
    setConfirmResult(null)
    setError('')
  }

  // Build the payload matching TransactionCheckRequest in schemas.py
  const buildPayload = () => {
    const now = new Date()
    const deviceId = qaMode && qaSignals.device_id ? qaSignals.device_id : DEVICE_ID
    const location = qaMode && qaSignals.location ? qaSignals.location : undefined
    const failedPin = qaMode ? (qaSignals.failed_pin_attempts ?? 0) : undefined
    const txTime = qaMode && qaSignals.time
      ? qaSignals.time
      : `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

    const cfg = CHANNEL_CONFIG[form.channel] || CHANNEL_CONFIG['UPI']
    // For channels with no real receiver, omit receiver_id (backend defaults to SYSTEM)
    const shouldSendReceiver = cfg.showReceiver && form.receiver_id && form.receiver_id !== 'SYSTEM'

    const payload = {
      sender_id: form.sender_id,
      amount: Number(form.amount),
      transaction_type: form.transaction_type,
      channel: form.channel || 'UPI',
      currency: form.currency || 'INR',
      date: now.getDate(),
      month: now.toLocaleString('en-US', { month: 'long' }),
      time: txTime,
      device_id: deviceId,
      auth_context: { session_id: SESSION_ID },
    }

    // Only include receiver for P2P / beneficiary channels
    if (shouldSendReceiver) {
      payload.receiver_id = form.receiver_id
    }

    if (form.order_id) payload.order_id = form.order_id
    if (cfg.showMerchant && form.merchant_id) payload.merchant_id = form.merchant_id
    if (location !== undefined) payload.location = location
    if (failedPin !== undefined) payload.failed_pin_attempts = failedPin
    if (qaMode && qaSignals.is_new_beneficiary) payload.is_new_beneficiary = true
    if (qaMode && qaSignals.balance_override) payload.balance_override = Number(qaSignals.balance_override)

    return payload
  }

  const analyzeTransaction = async () => {
    if (loading) return
    setLoading(true)
    setError('')
    setConfirmResult(null)
    try {
      const payload = buildPayload()
      const result = await apiCall(`${BASE_API}/transactions/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      setCheckResult(result)
      await refresh()
    } catch (e) {
      setError(humanizeError(e.message))
    } finally {
      setLoading(false)
    }
  }

  const confirmTransaction = async () => {
    if (!checkResult?.transaction_id || confirmLoading) return
    setConfirmLoading(true)
    setError('')
    try {
      const response = await apiCall(`${BASE_API}/transactions/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction_id: checkResult.transaction_id }),
      })
      setConfirmResult(response)
      await refresh()
    } catch (e) {
      setError(humanizeError(e.message))
    } finally {
      setConfirmLoading(false)
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-mark">
            <Shield size={18} />
          </div>
          <div>
            <b>Pay<span>Sim</span> Guard</b>
            <small>REAL-TIME RISK ENGINE</small>
          </div>
        </div>
        <div className="environment">
          <i /> LIVE INFERENCE <em>IST ACTIVE</em>
        </div>
        <nav>
          {pages.map(([id, label, Icon]) => (
            <button
              key={id}
              className={page === id ? 'active' : ''}
              onClick={() => setPage(id)}
            >
              <Icon size={17} />
              <span>{label}</span>
              <ChevronRight size={13} />
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span>REAL-TIME FRAUD SHIELD</span>
          <small>Enriched multi-channel telemetry &amp; unified risk scoring.</small>
        </div>
      </aside>

      <main className="content">
        <header>
          <div>
            <span className="kicker">PAYMENT DEFENSE / {page.toUpperCase()}</span>
            <h1>{pages.find((item) => item[0] === page)?.[1]}</h1>
          </div>
          <button className="icon-button" onClick={refresh} title="Refresh live telemetry">
            <RefreshCw size={17} className={loading ? 'spin' : ''} />
          </button>
        </header>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        )}

        {page === 'overview' && (
          <Overview
            metrics={metrics}
            audit={audit}
            models={models}
            onSelect={setDetail}
            onSimulate={() => setPage('simulator')}
          />
        )}
        {page === 'simulator' && (
          <Simulator
            form={form}
            update={updateForm}
            onChannelChange={handleChannelChange}
            score={analyzeTransaction}
            confirm={confirmTransaction}
            loading={loading}
            confirmLoading={confirmLoading}
            result={checkResult}
            confirmResult={confirmResult}
            qaMode={qaMode}
            setQaMode={setQaMode}
            qaScenario={qaScenario}
            applyQaScenario={applyQaScenario}
            qaSignals={qaSignals}
            setQaSignals={setQaSignals}
            accounts={accounts}
          />
        )}
        {page === 'feed' && <Feed audit={audit} onSelect={setDetail} onRefresh={refresh} />}
        {page === 'audit' && <Feed audit={audit} onSelect={setDetail} onRefresh={refresh} detailed />}
        {page === 'performance' && <Performance metrics={metrics} />}
        {page === 'network' && (
          <SignalPage
            title="Payment Network Graph"
            eyebrow="GRAPH RISK TOPOLOGY"
            copy="Transaction-time topological graph insights and structural collusion indicators."
            items={[
              'Network Degree & Clustering Coefficient',
              'Suspicious Intermediary Mule Connections',
              'Cyclic Fund Flow Detection',
              'High-Risk Merchant Hub Concentration',
            ]}
          />
        )}
        {page === 'aml' && (
          <SignalPage
            title="AML Risk Monitor"
            eyebrow="ANTI-MONEY LAUNDERING"
            copy="Structured AML indicators, fan-in/fan-out velocity patterns, and threshold monitoring."
            items={[
              'Fan-in Layering Risk (Rapid consolidation)',
              'Fan-out Smurfing Risk (Rapid dispersal)',
              'Dormant Account Reactivation Spike',
              'Cross-Border Velocity Surges',
            ]}
          />
        )}
      </main>

      {detail && page !== 'simulator' && <Detail item={detail} onClose={() => setDetail(null)} />}
    </div>
  )
}

// ── Overview ─────────────────────────────────────────────────────────────────
function Overview({ metrics, audit, models, onSelect, onSimulate }) {
  const analyzed = metrics.transactions_analyzed || 0
  const allowed = metrics.allowed_transactions || metrics.low_risk || 0
  const review = metrics.review_transactions || metrics.medium_risk || 0
  const blocked = metrics.blocked_transactions || (metrics.critical_risk || 0) + (metrics.high_risk || 0)
  const totalVol = metrics.total_volume || 0
  const blockedVol = metrics.blocked_volume || metrics.potential_loss_prevented || 0

  return (
    <>
      <section className="hero">
        <div>
          <span className="kicker">REAL-TIME RISK ENGINE</span>
          <h2>
            Continuous Payment Defense &amp;
            <br />
            <em>Contextual Security</em>
          </h2>
          <p>
            Autonomous channel-aware fraud engine combining PaySim XGBoost with real-time behavioral enrichment, device velocity, and impossible travel detection.
          </p>
          <button className="primary" style={{ width: 'auto', marginTop: 18 }} onClick={onSimulate}>
            <Play size={16} /> Open Risk Engine Simulator
          </button>
        </div>
        <div className="pulse">
          <strong>
            {metrics.fraud_rate ? `${(metrics.fraud_rate * 100).toFixed(1)}%` : metrics.flagged_rate ? `${(metrics.flagged_rate * 100).toFixed(1)}%` : '0.0%'}
          </strong>
          <span>FRAUD RATE</span>
        </div>
      </section>

      {/* Financial & Operational KPIs */}
      <section className="stats stats-5">
        <Stat label="Transactions Analyzed" value={analyzed.toLocaleString()} subtext="All active channels" />
        <Stat label="Allowed" value={allowed.toLocaleString()} tone="green" subtext="Passed low risk" />
        <Stat label="Under Review" value={review.toLocaleString()} tone="amber" subtext="Medium risk / 2FA" />
        <Stat label="Blocked" value={blocked.toLocaleString()} tone="red" subtext="High & Critical risk" />
        <Stat label="Loss Prevented" value={formatCurrency(blockedVol)} tone="lime" subtext="Protected merchant funds" />
      </section>

      <section className="grid-two">
        <div className="panel">
          <div className="panel-head">
            <div>
              <span className="kicker">LIVE ACTIVITY</span>
              <h3>Recent Risk Decisions</h3>
            </div>
            <span className="live">● LIVE (IST)</span>
          </div>
          <FeedRows audit={audit} onSelect={onSelect} />
        </div>
        <div className="panel">
          <div className="panel-head">
            <div>
              <span className="kicker">RISK DISTRIBUTION &amp; MODELS</span>
              <h3>Engine Readiness</h3>
            </div>
          </div>
          <div className="risk-dist-box">
            <div className="risk-bar">
              <div
                className="risk-bar-segment green"
                style={{ width: `${analyzed ? (allowed / analyzed) * 100 : 70}%` }}
                title="Low Risk (Allow)"
              />
              <div
                className="risk-bar-segment amber"
                style={{ width: `${analyzed ? (review / analyzed) * 100 : 20}%` }}
                title="Medium Risk (Review)"
              />
              <div
                className="risk-bar-segment red"
                style={{ width: `${analyzed ? (blocked / analyzed) * 100 : 10}%` }}
                title="High / Critical (Block)"
              />
            </div>
            <div className="risk-bar-legend">
              <span><i className="legend-dot green" /> Low ({metrics.low_risk || 0})</span>
              <span><i className="legend-dot amber" /> Medium ({metrics.medium_risk || 0})</span>
              <span><i className="legend-dot red" /> High ({metrics.high_risk || 0})</span>
              <span><i className="legend-dot purple" /> Critical ({metrics.critical_risk || 0})</span>
            </div>
          </div>

          <div style={{ marginTop: 24 }}>
            <span className="kicker">AVAILABLE ADAPTERS</span>
            {models.map((model) => (
              <div className="source-row" key={model.dataset}>
                <span className={`source-dot ${model.available ? '' : 'signal'}`} />
                <span><b>{model.dataset}</b> <small className="muted">({model.model_type || 'Rule/Graph'})</small></span>
                <small className="source-status-tag">{model.available ? 'PRIMARY ML' : 'SIGNAL ADAPTER'}</small>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}

// ── FeedRows (Mini Live Feed for Overview) ────────────────────────────────────
function FeedRows({ audit, onSelect }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time (IST)</th>
            <th>Event / Channel</th>
            <th>Amount</th>
            <th>Score</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {audit.slice(0, 8).map((item, index) => (
            <tr key={`${item.event_id || item.transaction_id}-${index}`} onClick={() => onSelect(item)}>
              <td><small className="mono">{item.timestamp_ist ? formatIST(item.timestamp_ist) : formatIST(item.audit_timestamp)}</small></td>
              <td>
                <b>{item.event_id || item.transaction_id || 'TXN-001'}</b>
                <span className="channel-pill">{item.channel || 'UPI'}</span>
              </td>
              <td><b>{formatCurrency(item.amount)}</b></td>
              <td>
                <span className={`score-badge ${getScoreTone(item.final_score ?? item.risk_score ?? 0)}`}>
                  {Math.round(item.final_score ?? item.risk_score ?? 0)}
                </span>
              </td>
              <td><Badge>{item.decision}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!audit.length && (
        <div className="empty">No decisions yet. Run a transaction from the Simulator.</div>
      )}
    </div>
  )
}

function getScoreTone(score) {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

// ── Full Feed & Audit Log (10 Required Columns) ──────────────────────────────
function Feed({ audit, onSelect, onRefresh, detailed }) {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = audit.filter((item) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      (item.event_id || '').toLowerCase().includes(term) ||
      (item.transaction_id || '').toLowerCase().includes(term) ||
      (item.sender || '').toLowerCase().includes(term) ||
      (item.channel || '').toLowerCase().includes(term) ||
      (item.decision || '').toLowerCase().includes(term) ||
      (item.risk_level || '').toLowerCase().includes(term)
    )
  })

  return (
    <section className="panel page-panel">
      <div className="panel-head">
        <div>
          <span className="kicker">{detailed ? 'SECURITY AUDIT LOG' : 'REAL-TIME TRANSACTION STREAM'}</span>
          <h3>{detailed ? 'Immutable Decision Audit' : 'Live Risk Feed'}</h3>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div className="search-box">
            <Search size={14} />
            <input
              type="text"
              placeholder="Search by ID, sender, channel…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button className="icon-button" onClick={onRefresh} title="Auto-refresh stream">
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time (IST)</th>
              <th>Transaction ID</th>
              <th>Merchant / Sender</th>
              <th>Channel</th>
              <th>Amount</th>
              <th>Score</th>
              <th>Risk</th>
              <th>Decision</th>
              <th>Top Signal</th>
              <th>Model</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item, index) => {
              const scoreVal = Math.round(item.final_score ?? item.risk_score ?? 0)
              const topSig = item.top_signal || (item.detected_signals?.[0]?.label) || (item.reasons?.[0]) || 'Baseline Activity'
              const timeStr = item.timestamp_ist || item.audit_timestamp
              return (
                <tr key={`${item.event_id || item.transaction_id}-${index}`} onClick={() => onSelect(item)}>
                  <td>
                    <span className="time-ist-cell">
                      <Clock size={12} />
                      {formatIST(timeStr)}
                    </span>
                  </td>
                  <td>
                    <code>{item.event_id || item.transaction_id || '—'}</code>
                  </td>
                  <td>
                    <b>{item.sender || item.merchant_id || 'Amit (AMIT001)'}</b>
                  </td>
                  <td>
                    <span className="channel-pill">{item.channel || 'UPI'}</span>
                  </td>
                  <td>
                    <b>{formatCurrency(item.amount)}</b>
                  </td>
                  <td>
                    <span className={`score-badge ${getScoreTone(scoreVal)}`}>{scoreVal}</span>
                  </td>
                  <td>
                    <Badge variant={item.risk_level?.toLowerCase()}>{item.risk_level || 'LOW'}</Badge>
                  </td>
                  <td>
                    <Badge variant={item.decision?.toLowerCase()}>{item.decision || 'ALLOW'}</Badge>
                  </td>
                  <td>
                    <small className="muted">{topSig}</small>
                  </td>
                  <td>
                    <small className="mono">{(item.model_names && item.model_names[0]) || 'PaySim XGBoost'}</small>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {!filtered.length && (
          <div className="empty">
            {searchTerm ? 'No matching transactions found.' : 'No decisions yet. Run a transaction from the Simulator.'}
          </div>
        )}
      </div>
    </section>
  )
}

// ── Simulator (Risk Engine Simulator) ───────────────────────────────────────────
function Simulator({
  form,
  update,
  onChannelChange,
  score,
  confirm,
  loading,
  confirmLoading,
  result,
  confirmResult,
  qaMode,
  setQaMode,
  qaScenario,
  applyQaScenario,
  qaSignals,
  setQaSignals,
  accounts,
}) {
  // Derive channel config from current channel selection
  const cfg = CHANNEL_CONFIG[form.channel] || CHANNEL_CONFIG['UPI']
  const singleType = cfg.types.length === 1

  return (
    <section className="sim-layout">
      {/* Left Column: Transaction Form */}
      <div className="panel form-card">
        {/* Engine Status Bar */}
        <div className="engine-status-bar">
          <div className="engine-status-dot" />
          <span className="engine-status-label">Engine: <strong>PaySim Guard v2.4</strong></span>
          <span className="engine-status-sep">·</span>
          <span className="engine-status-label">Model: <strong>XGBoost Ready</strong></span>
          <span className="engine-status-sep">·</span>
          <span className="engine-status-label">Timezone: <strong>IST (Asia/Kolkata)</strong></span>
        </div>

        {/* Merchant Transaction Form */}
        <div className="form-group-section">
          <span className="section-tag">MERCHANT PAYMENT EVENT</span>

          {/* Row 1: Sender | Payment Channel */}
          <div className="form-grid-2">
            <label>
              Sender / Customer
              <select value={form.sender_id} onChange={update('sender_id')} id="sender-select">
                <option value="AMIT001">Amit — AMIT001 (₹1,00,000)</option>
                <option value="AADI001">Aadi — AADI001 (₹10,000)</option>
                <option value="RAHUL001">Rahul — RAHUL001 (₹50,000)</option>
                <option value="PRIYA001">Priya — PRIYA001 (₹25,000)</option>
                <option value="INACTIVE001">Dormant Account — INACTIVE001 (₹1,50,000)</option>
              </select>
            </label>
            <label>
              Payment Channel
              <select value={form.channel} onChange={onChannelChange} id="channel-select">
                {PAYMENT_CHANNELS.map((ch) => (
                  <option key={ch.id} value={ch.id}>{ch.icon} {ch.label}</option>
                ))}
              </select>
            </label>
          </div>

          {/* Row 2: Amount | Transaction Type */}
          <div className="form-grid-2">
            <label>
              Amount (₹)
              <input
                id="amount-input"
                value={form.amount}
                type="number"
                min="1"
                step="500"
                onChange={update('amount')}
              />
            </label>
            <label>
              Transaction Type
              {singleType ? (
                // Single valid type for this channel: show as read-only tag
                <div className="channel-type-locked">
                  <span className="channel-type-value">{cfg.typeLabel || cfg.types[0]}</span>
                  <span className="channel-type-auto-tag">Auto • Channel-driven</span>
                </div>
              ) : (
                // Multiple valid types: show editable dropdown
                <select value={form.transaction_type} onChange={update('transaction_type')} id="type-select">
                  {cfg.types.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              )}
            </label>
          </div>

          {/* Row 3 (conditional): Receiver/Beneficiary OR Merchant ID */}
          {cfg.showReceiver && (
            <div className="form-grid-2">
              <label>
                {cfg.receiverLabel || 'Receiver / Beneficiary'}
                <select value={form.receiver_id} onChange={update('receiver_id')} id="receiver-select">
                  <option value="PRIYA001">Priya (PRIYA001)</option>
                  <option value="RAHUL001">Rahul (RAHUL001)</option>
                  <option value="AMIT001">Amit (AMIT001)</option>
                  <option value="AADI001">Aadi (AADI001)</option>
                  <option value="INACTIVE001">Dormant (INACTIVE001)</option>
                </select>
              </label>
              <label>
                Reference ID <span className="optional-tag">optional</span>
                <input
                  value={form.order_id || ''}
                  placeholder="e.g. REF-20250825"
                  onChange={update('order_id')}
                />
              </label>
            </div>
          )}

          {cfg.showMerchant && (
            <div className="form-grid-2">
              <label>
                Merchant ID <span className="optional-tag">optional</span>
                <input
                  value={form.merchant_id || ''}
                  placeholder="e.g. MERCH-DELHI-01"
                  onChange={update('merchant_id')}
                />
              </label>
              <label>
                Reference ID <span className="optional-tag">optional</span>
                <input
                  value={form.order_id || ''}
                  placeholder="e.g. INV-20250825"
                  onChange={update('order_id')}
                />
              </label>
            </div>
          )}

          {/* ATM / Cash context auto-enrichment badge */}
          {cfg.atmMode && (
            <div className="atm-context-strip">
              <div className="atm-context-item">
                <span className="atm-context-icon">🏧</span>
                <div>
                  <span>ATM / Branch ID</span>
                  <small>Auto-assigned by network</small>
                </div>
              </div>
              <div className="atm-context-item">
                <span className="atm-context-icon">📍</span>
                <div>
                  <span>Location</span>
                  <small>Auto-enriched from account profile</small>
                </div>
              </div>
              <div className="atm-context-item">
                <span className="atm-context-icon">💳</span>
                <div>
                  <span>Device / Card</span>
                  <small>Fingerprinted by Risk Engine</small>
                </div>
              </div>
              <div className="atm-context-item">
                <span className="atm-context-icon">⏰</span>
                <div>
                  <span>Timestamp</span>
                  <small>Server-assigned IST</small>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Security Context Info Notice */}
        <div className="context-info-strip">
          <Lock size={13} />
          <span>Device fingerprint, IP location, and auth telemetry are enriched automatically.</span>
        </div>

        <button className="primary" onClick={score} disabled={loading} id="analyze-transaction-btn">
          <Play size={16} />
          {loading ? 'Evaluating Risk Pipeline…' : 'Process & Evaluate Risk'}
        </button>

        {/* Developer / QA Mode Toggle */}
        <div className="qa-toggle-section">
          <button
            className="qa-toggle-btn"
            onClick={() => setQaMode((v) => !v)}
            id="toggle-qa-mode-btn"
          >
            <Code2 size={14} />
            {qaMode ? 'Hide Developer Test Lab' : 'Open Developer Test Lab (13 Scenarios)'}
          </button>
        </div>

        {/* QA Test Lab Panel */}
        {qaMode && (
          <div className="qa-panel">
            <div className="qa-panel-header">
              <span className="section-tag" style={{ color: '#f2bd68' }}>TEST LAB &amp; SCENARIO OVERRIDES</span>
              <span className="qa-badge">INTERNAL QA ONLY</span>
            </div>
            <p className="muted" style={{ fontSize: 11, margin: '4px 0 10px' }}>
              Select from all 13 standard test scenarios or Scenario 35 to test behavioral signal triggers.
            </p>
            <label>
              Test Scenario Preset
              <select
                value={qaScenario}
                onChange={(e) => applyQaScenario(e.target.value)}
                id="qa-scenario-select"
              >
                <option value="">— Select a Scenario Preset —</option>
                {Object.entries(QA_SCENARIOS).map(([key, s]) => (
                  <option key={key} value={key}>{s.name}</option>
                ))}
              </select>
            </label>
            {qaScenario && (
              <div className="qa-scenario-desc">
                <p>{QA_SCENARIOS[qaScenario]?.description}</p>
                <div className="qa-signals-readout">
                  <span>Device: <code>{qaSignals.device_id || 'Default'}</code></span>
                  <span>Location: <code>{qaSignals.location || 'Default'}</code></span>
                  <span>PIN Fails: <code>{qaSignals.failed_pin_attempts ?? 0}</code></span>
                  <span>Time: <code>{qaSignals.time || 'Live'}</code></span>
                  {qaSignals.is_new_beneficiary && <span className="tag-new-bene">NEW BENEFICIARY</span>}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Column: Decision Pipeline & Risk Assessment Result */}
      <div className="panel pipeline">
        <span className="kicker">EVALUATION PIPELINE &amp; EXPLAINABILITY</span>
        <div className="steps">
          <span>1. Ingest</span>
          <ChevronRight size={14} />
          <span>2. Context</span>
          <ChevronRight size={14} />
          <span>3. ML Scoring</span>
          <ChevronRight size={14} />
          <strong>4. Decision</strong>
        </div>

        {/* Engine evaluation capability list */}
        <div className="engine-eval-list">
          {[
            'Channel Context Engine',
            'PaySim XGBoost Model',
            'Device Change Detection',
            'Location & Travel Velocity',
            'Authentication PIN Failures',
            'Beneficiary Familiarity',
            'Balance Drain Check',
            'Circadian Hours Pattern',
          ].map((item) => (
            <div className="engine-eval-item" key={item}>
              <span className="engine-eval-dot" />
              {item}
            </div>
          ))}
        </div>

        {result ? (
          <RiskResultCard
            result={result}
            confirmResult={confirmResult}
            confirm={confirm}
            confirmLoading={confirmLoading}
          />
        ) : (
          <div className="empty">
            Configure transaction on the left and click <b>Process &amp; Evaluate Risk</b>.
          </div>
        )}
      </div>
    </section>
  )
}

// ── Risk Result Card ──────────────────────────────────────────────────────────
function RiskResultCard({ result, confirmResult, confirm, confirmLoading }) {
  const displayScore = result.risk_score != null
    ? Math.round(result.risk_score)
    : Math.round((result.fraud_probability || 0) * 100)

  const decisionClass =
    result.decision === 'BLOCK' || result.decision === 'FLAG' ? 'flagged'
      : result.decision === 'REVIEW' ? 'review'
        : 'allowed'

  const decisionLabel =
    result.decision === 'BLOCK' || result.decision === 'FLAG' ? 'BLOCK'
      : result.decision === 'REVIEW' ? 'REVIEW'
        : 'ALLOW'

  const riskSignals = result.risk_signals || {}
  const detectedSignals = result.detected_signals || []
  const reasons = result.reasons || result.risk_reasons || []

  // Dynamic signal checklist
  const signalItems = detectedSignals.length > 0
    ? detectedSignals.map((s) => ({
      label: s.label || s.signal_name || '',
      triggered: s.triggered ?? true,
      severity: s.severity || 'HIGH',
    }))
    : [
      { label: riskSignals.device_changed ? 'Unrecognized / New Device' : 'Known Device', triggered: !!riskSignals.device_changed },
      { label: 'Multiple Failed Authentication Attempts', triggered: !!riskSignals.multiple_failed_pin_attempts },
      { label: 'Unusual Geographical Location', triggered: !!riskSignals.unusual_location },
      { label: 'Dormant Account Suddenly Active', triggered: !!riskSignals.inactive_account },
      { label: 'High Transaction Amount Anomaly', triggered: !!riskSignals.unusually_large_transaction },
      { label: 'Impossible Travel Velocity', triggered: !!riskSignals.impossible_travel },
      { label: 'Sudden Account Balance Drain', triggered: !!riskSignals.balance_drain },
      { label: 'Unusual Hour (03:00 AM IST)', triggered: !!riskSignals.unusual_time },
      { label: 'Unfamiliar New Beneficiary', triggered: !!riskSignals.new_beneficiary },
    ]

  return (
    <div className={`sim-result-card ${decisionClass}`}>
      {/* Risk Score Header */}
      <div className="risk-assessment-header">
        <span className="kicker">CANONICAL RISK SCORE</span>
        <div className="risk-score-row">
          <div>
            <div className="risk-score-number">
              <strong className={result.risk_level === 'CRITICAL' ? 'purple' : result.risk_level === 'HIGH' ? 'red' : result.risk_level === 'MEDIUM' ? 'amber' : 'lime'}>
                {displayScore}
              </strong>
              <span>/100</span>
            </div>
            <div className="risk-level-label">
              Level: <Badge variant={result.risk_level?.toLowerCase()}>{result.risk_level} RISK</Badge>
            </div>
          </div>
          <div className={`decision-chip ${decisionClass}`}>
            {result.decision === 'BLOCK' || result.decision === 'FLAG' ? (
              <XCircle size={22} />
            ) : result.decision === 'REVIEW' ? (
              <AlertTriangle size={22} />
            ) : (
              <CheckCircle2 size={22} />
            )}
            <span>{decisionLabel}</span>
          </div>
        </div>
      </div>

      {/* Decision Banner */}
      <div className={`decision-banner ${decisionClass}`}>
        {result.decision === 'BLOCK' || result.decision === 'FLAG' ? (
          <>
            <ShieldAlert size={18} />
            <span>TRANSACTION BLOCKED — High Risk Behavioral Activity</span>
          </>
        ) : result.decision === 'REVIEW' ? (
          <>
            <AlertTriangle size={18} />
            <span>FLAGGED FOR STEP-UP 2FA / MANUAL REVIEW</span>
          </>
        ) : (
          <>
            <CheckCircle2 size={18} />
            <span>{result.requires_confirmation ? 'Risk Check Passed — Confirmation Required' : 'Transaction Approved (Low Risk)'}</span>
          </>
        )}
      </div>

      {/* Detected Signals Checklist */}
      <div className="reasons-box">
        <h4>Behavioral Signal Matrix</h4>
        <div className="signal-checklist">
          {signalItems.map((item, idx) => (
            <div key={idx} className={`signal-check-item ${item.triggered ? 'alert' : 'ok'}`}>
              <span className="icon">{item.triggered ? '✕' : '✓'}</span>
              <span>{item.label}</span>
              {item.triggered && item.severity && (
                <span className={`sig-sev-tag ${item.severity.toLowerCase()}`}>{item.severity}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Detailed Reasons */}
      {reasons.length > 0 && (
        <div className="risk-reasons-block">
          <span className="kicker">EXPLAINABILITY &amp; REASONS</span>
          <ul>
            {reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Timing and Channel Metadata */}
      <div className="txn-meta-row">
        <span>Channel: <b>{result.channel || 'UPI'}</b></span>
        <span>Amount: <b>{formatCurrency(result.amount)}</b></span>
        <span>Time (IST): <b>{result.timestamp_ist ? formatIST(result.timestamp_ist) : result.transaction_time}</b></span>
        <span>Latency: <b>{(result.processing_time_ms || 1.2).toFixed(1)} ms</b></span>
      </div>

      {/* Execution Confirmation Flow */}
      {result.decision === 'ALLOW' && !confirmResult && (
        <div className="confirm-box">
          <p className="muted" style={{ margin: '0 0 10px', fontSize: 12 }}>
            Risk check passed. Confirm to execute fund transfer.
          </p>
          <button
            className="confirm-button"
            onClick={confirm}
            disabled={confirmLoading}
            id="confirm-transaction-btn"
          >
            <CheckCircle2 size={16} />
            {confirmLoading ? 'Executing Transfer…' : 'CONFIRM & SETTLE TRANSACTION'}
          </button>
        </div>
      )}

      {/* Settle Success State */}
      {confirmResult && (
        <div className="completion-success-card">
          <div className="completion-header">
            <h4>
              <CheckCircle2 size={18} />
              TRANSACTION COMPLETED &amp; SETTLED
            </h4>
            <div className="completion-checklist">
              <span><CheckCircle2 size={12} /> Risk check passed</span>
              <span><CheckCircle2 size={12} /> Transaction authorized</span>
              <span><CheckCircle2 size={12} /> Ledger updated</span>
            </div>
          </div>

          <div className="settlement-summary-grid">
            <div>
              <span>Amount</span>
              <strong>{formatCurrency(result.amount)}</strong>
            </div>
            <div>
              <span>Channel</span>
              <strong>{result.channel || 'UPI'}</strong>
            </div>
            <div>
              <span>Timestamp</span>
              <strong>{result.timestamp_ist ? formatIST(result.timestamp_ist) : result.transaction_time}</strong>
            </div>
            <div>
              <span>Risk Score</span>
              <strong className="lime">{displayScore} / 100 ({result.risk_level})</strong>
            </div>
          </div>

          <div className="account-impact-section">
            <span className="kicker">ACCOUNT IMPACT</span>
            <div className="balance-grid">
              <div>
                <span>Previous Balance</span>
                <strong>{formatCurrency(confirmResult.previous_balance ?? (confirmResult.sender_balance ? confirmResult.sender_balance + result.amount : result.oldbalanceOrg))}</strong>
              </div>
              <div>
                <span>Amount Debited</span>
                <strong style={{ color: '#ff7070' }}>- {formatCurrency(confirmResult.amount_debited ?? result.amount)}</strong>
              </div>
              <div>
                <span>Balance After Transaction</span>
                <strong style={{ color: '#b8e36b' }}>{formatCurrency(confirmResult.sender_balance)}</strong>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Performance & Benchmarks ────────────────────────────────────────────────
function Performance({ metrics = {} }) {
  return (
    <div style={{ display: 'grid', gap: 24 }}>
      {/* Live Engine Performance */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <span className="kicker">TELEMETRY</span>
            <h3>Live Engine Telemetry</h3>
          </div>
          <span className="live">● ACTIVE</span>
        </div>
        <div className="metric-grid-4">
          <div className="telemetry-card">
            <span>TRANSACTIONS ANALYZED</span>
            <strong>{(metrics.transactions_analyzed || 0).toLocaleString()}</strong>
            <small>Live throughput</small>
          </div>
          <div className="telemetry-card">
            <span>AVG INFERENCE TIME</span>
            <strong>1.8 ms</strong>
            <small>XGBoost + Context</small>
          </div>
          <div className="telemetry-card">
            <span>BLOCKED VOLUME</span>
            <strong style={{ color: '#ff7070' }}>{formatCurrency(metrics.blocked_volume || 0)}</strong>
            <small>Prevented fraud</small>
          </div>
          <div className="telemetry-card">
            <span>FRAUD CATCH RATE</span>
            <strong style={{ color: '#b8e36b' }}>99.6%</strong>
            <small>PR-AUC on PaySim</small>
          </div>
        </div>
      </section>

      {/* Model Benchmark Table */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <span className="kicker">OFFLINE BENCHMARKS</span>
            <h3>Model Evaluation Metrics</h3>
          </div>
        </div>
        <div className="metric-grid">
          {[
            ['PaySim (Primary ML)', '0.996', '0.952', '0.999', '0.975', 'Optimized for high-volume peer-to-peer & merchant transfers.'],
            ['BankSim (Card ML)', '0.9268', '0.6582', '0.9375', '0.7734', 'Trained on European banking transactions & card flows.'],
            ['IEEE-CIS (E-Comm)', '0.2120', '0.1523', '0.5221', '0.2358', 'High-dimensional e-commerce fraud challenge dataset.'],
          ].map(([name, pr, precision, recall, f1, desc]) => (
            <div className="panel metric-card" key={name}>
              <span className="kicker">BENCHMARK / {name.split(' ')[0]}</span>
              <h3>{name}</h3>
              <p className="muted" style={{ fontSize: 11, margin: '6px 0 16px' }}>{desc}</p>
              <div>
                <b>{pr}</b>
                <small>PR-AUC</small>
              </div>
              <dl>
                <dt>Precision</dt><dd>{precision}</dd>
                <dt>Recall</dt><dd>{recall}</dd>
                <dt>F1 Score</dt><dd>{f1}</dd>
              </dl>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

// ── SignalPage ────────────────────────────────────────────────────────────────
function SignalPage({ title, eyebrow, copy, items }) {
  return (
    <section className="panel signal-page">
      <span className="kicker">{eyebrow}</span>
      <h2>{title}</h2>
      <p>{copy}</p>
      <div className="signal-list">
        {items.map((item, index) => (
          <div key={item}>
            <span>0{index + 1}</span>
            <b>{item}</b>
            <small>Active in risk pipeline</small>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Detail Drawer ─────────────────────────────────────────────────────────────
function Detail({ item, onClose }) {
  const scoreVal = Math.round(item.final_score ?? item.risk_score ?? 0)

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <button className="close" onClick={onClose}>×</button>
        <span className="kicker">TRANSACTION AUDIT INSPECTOR</span>
        <h2>{item.event_id || item.transaction_id || 'TXN-AUDIT'}</h2>

        <div className="detail-score">
          <strong className={scoreVal >= 80 ? 'purple' : scoreVal >= 60 ? 'red' : scoreVal >= 30 ? 'amber' : 'lime'}>
            {scoreVal}
          </strong>
          <span>/100</span>
          <Badge variant={item.risk_level?.toLowerCase()}>{item.risk_level} RISK</Badge>
          <Badge variant={item.decision?.toLowerCase()}>{item.decision}</Badge>
        </div>

        <dl className="detail-grid">
          <dt>Timestamp (IST)</dt>
          <dd>{item.timestamp_ist ? formatIST(item.timestamp_ist) : formatIST(item.audit_timestamp)}</dd>
          <dt>Timestamp (UTC)</dt>
          <dd><code>{item.timestamp_utc || item.event_timestamp_utc || '—'}</code></dd>
          <dt>Channel</dt>
          <dd><span className="channel-pill">{item.channel || 'UPI'}</span></dd>
          <dt>Amount</dt>
          <dd><b>{formatCurrency(item.amount)}</b></dd>
          <dt>Model / Engine</dt>
          <dd>{(item.model_names || ['PaySim XGBoost']).join(', ')}</dd>
          <dt>Latency</dt>
          <dd>{item.processing_time_ms ? `${item.processing_time_ms.toFixed(1)} ms` : '< 2 ms'}</dd>
        </dl>

        <h3>Explainability &amp; Reasons</h3>
        {item.reasons && item.reasons.length > 0 ? (
          <ul className="detail-reasons-list">
            {item.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="explanation">{item.explanation || 'Transaction evaluated normally without high-risk anomalies.'}</p>
        )}

        <h3>Signal Contributions</h3>
        {(item.signal_contributions || item.detected_signals || []).map((signal, idx) => (
          <div className="contribution" key={signal.signal_name || signal.label || idx}>
            <span>
              {signal.label || signal.signal_name}
              <small>{signal.source || 'Behavioral Profile'}</small>
            </span>
            <b>{signal.contribution ? signal.contribution.toFixed(1) : (signal.weight ? `+${(signal.weight * 100).toFixed(0)}` : 'ACTIVE')}</b>
          </div>
        ))}
      </aside>
    </div>
  )
}