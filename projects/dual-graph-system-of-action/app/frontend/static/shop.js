/*
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

const LANG_STORAGE_KEY = 'soa_ui_lang';
const CHAT_HISTORY_STORAGE_KEY = 'soa_chat_history_by_user';
const PENDING_ORDER_STORAGE_KEY = 'soa_pending_order_by_user';
const ACTIVE_USER_STORAGE_KEY = 'soa_active_user_id';

const SHOP_I18N = {
  en: {
    pageTitle:
      'TheLook Shopping Mall & Support Chat | Dual-Graph System of Action',
    headerTitle: 'TheLook Shopping Mall & ADK 2.0 Refund Assistant',
    headerSubtitle:
      'Cloud Spanner OperationalContextGraph (R2G + U2G) & Knowledge Catalog',
    navShop: 'UI 1: Shopping Mall (/shop)',
    navConsole: 'UI 2: Data Engineer Console (/console)',
    langBtnText: '\uD83C\uDF10 한국어 (KO)',
    langBtnTitle:
      'Switch language to Korean and reset demo dataset ' +
      '(한국어로 전환 및 데모 ' +
      '데이터 초기화)',
    resetBtnText: 'Reset Demo Data',
    sec1Title: '1. Active Customer Persona Switcher',
    sec1Subtitle: 'Session Identity Bound Outside LLM Prompt',
    sec2Title: '2. Customer Orders & Live Spanner Status',
    sec3Title: '3. TheLook Product Catalog & Fulfillment Centers',
    sec3Subtitle: 'Governed by POL-REFUND-STD-V1',
    chatTitle: 'ADK 2.0 Autonomous Refund Support Chat',
    chatSubtitle:
      'Evaluates Cloud Spanner ISO GQL + Knowledge Catalog Loyalty Tier Policy',
    clearChatLabel: 'Clear Chat',
    clearChatTitle: 'Clear current customer\'s chat history',
    promptChipsHeading: '1-Click Persona Prompt Chips:',
    chatInputPlaceholder:
      'Ask for a refund (e.g., Please refund order ORD-90124)...',
    sendBtn: 'Send',
    runningBtn: 'Running...',
    returns100dLabel: '100d Returns:',
    deliveredLabel: 'Delivered:',
    inTransitText: 'In Transit (Not Delivered)',
    dcPrefix: 'DC:',
    customerPrefix: 'Customer',
    orderAmountPrefix: 'Order Amount:',
    clickToRefundPrefix: 'Click to request refund',
    telemetryHeading: 'Workflow Telemetry & Lineage Metadata',
    inspectConsoleLink: 'Inspect in Data Engineer Console (\u2192)',
    loadingTitle: 'Evaluating Dual-Graph Policy & Lineage...',
    loadingDesc:
      'Traversing Cloud Spanner OperationalContextGraph (ISO GQL), resolving' +
      ' Knowledge Catalog contract, and recording BigQuery ActionLineageGraph' +
      ' trace...',
    replyConfirmRequired: 'Agent Message \u2014 Customer Confirmation Required',
    replyAwaitingOrder:
      'Agent Message \u2014 Awaiting Order or Refund Request',
    replyOrderList: 'Agent Message \u2014 Customer Order History',
    replyOrderInfo: 'Agent Message \u2014 Order Status & Details',
    replyPolicyInfo: 'Agent Message \u2014 Return Policy & Support Info',
    replyDefault: 'Agent Message',
    confirmBtnPrefix: 'Confirm Refund:',
    cancelBtnLabel: 'No, choose a different order',
    requestRefundBtnPrefix: 'Request Refund:',
    confirmPromptTemplate: (oid) =>
      `Yes, confirm refund for order ORD-${oid}.`,
    cancelPromptText: 'No, I want to refund a different order.',
    requestRefundPromptTemplate: (oid) =>
      `Please refund my order ORD-${oid}.`,
    resetConfirmBadge: 'Confirm Demo Reset',
    resetConfirmHeading: 'Are you sure you want to reset all demo data?',
    resetConfirmDescHtml:
      'This will restore Cloud Spanner demo orders ' +
      '(<code class="font-mono font-semibold">ORD-90124</code>, ' +
      '<code class="font-mono font-semibold">ORD-90125</code>, ' +
      '<code class="font-mono font-semibold">ORD-90126</code>, ' +
      '<code class="font-mono font-semibold">ORD-90588</code>, ' +
      '<code class="font-mono font-semibold">ORD-90910</code>), refresh all ' +
      'relative 30-day delivery and 100-day return timestamps to current UTC ' +
      'time, and clear all BigQuery ' +
      '<code class="font-mono font-semibold">soa_action_lineage</code> ' +
      'audit traces.',
    resetCancelBtn: 'Cancel',
    resetConfirmBtn: 'Yes, Reset Demo Data',
    langSwitchBadge: 'Language Switch & Demo Dataset Reset',
    langSwitchHeading:
      'Switch UI language to Korean (한국어) and reset demo data?',
    langSwitchDescHtml:
      'Changing the language will <strong>reset the demo dataset</strong> ' +
      'so all orders, timestamps, chat messages, and BigQuery ' +
      '<code class="font-mono font-semibold">soa_action_lineage</code> ' +
      'traces start cleanly in Korean.<br><span class="text-slate-500">' +
      '(언어를 한국어로 변경하면 ' +
      'Cloud Spanner 주문 상태, 채팅 내역 ' +
      '및 BigQuery 리니지 트레이스가 ' +
      '모두 초기화됩니다.)</span>',
    langSwitchConfirmBtn:
      'Switch to Korean & Reset Demo Data (한국어 전환)',
    resetRunningBadge: 'Dual-Graph Demo Reset',
    resetRunningTitle: 'Resetting Cloud Spanner & BigQuery Demo State...',
    resetRunningPrep:
      'Preparing Dual-Graph System of Action reset sequence...',
  },
  ko: {
    pageTitle:
      'TheLook 쇼핑몰 & 고객지원 채팅 | ' +
      'Dual-Graph System of Action',
    headerTitle:
      'TheLook 쇼핑몰 & ADK 2.0 환불 어시스' +
      '턴트',
    headerSubtitle:
      'Cloud Spanner OperationalContextGraph (R2G + U2G) & Knowledge Catalog',
    navShop: 'UI 1: 쇼핑몰 (/shop)',
    navConsole: 'UI 2: 데이터 엔지니어 ' +
      '콘솔 (/console)',
    langBtnText: '\uD83C\uDF10 English (EN)',
    langBtnTitle:
      '영어로 전환 및 데모 데이터' +
      ' 초기화 (Switch language to English and reset demo data)',
    resetBtnText: '데모 데이터 초기화',
    sec1Title: '1. 활성 고객 페르소나 ' +
      '선택',
    sec1Subtitle:
      'LLM 프롬프트 외부에 바인딩' +
      '된 세션 ID',
    sec2Title:
      '2. 고객 주문 내역 및 실시간 ' +
      'Spanner 상태',
    sec3Title:
      '3. TheLook 상품 카탈로그 및 물류 ' +
      '센터',
    sec3Subtitle: 'POL-REFUND-STD-V1 정책 적용',
    chatTitle: 'ADK 2.0 자율 환불 지원 채팅',
    chatSubtitle:
      'Cloud Spanner ISO GQL + Knowledge Catalog 고객 등급 ' +
      '정책 평가',
    clearChatLabel: '대화 지우기',
    clearChatTitle: '현재 고객의 채팅 내역' +
      ' 지우기',
    promptChipsHeading:
      '원클릭 페르소나 프롬프트 ' +
      '칩:',
    chatInputPlaceholder:
      '환불을 요청하세요 (예: 주문' +
      ' ORD-90124 환불 요청합니다)...',
    sendBtn: '전송',
    runningBtn: '실행 중...',
    returns100dLabel: '100일 내 반품:',
    deliveredLabel: '배송 완료일:',
    inTransitText: '배송 중 (미배달)',
    dcPrefix: '물류센터:',
    customerPrefix: '고객',
    orderAmountPrefix: '주문 금액:',
    clickToRefundPrefix: '클릭하여 환불 요청',
    telemetryHeading:
      '워크플로 텔레메트리 및 ' +
      '리니지 메타데이터',
    inspectConsoleLink:
      '데이터 엔지니어 콘솔에서 ' +
      '상세 분석 (\u2192)',
    loadingTitle:
      '듀얼 그래프 정책 및 리니지' +
      ' 평가 중...',
    loadingDesc:
      'Cloud Spanner OperationalContextGraph (ISO GQL) 탐색, ' +
      'Knowledge Catalog 시맨틱 계약 확인 및 ' +
      'BigQuery ActionLineageGraph 트레이스 기록 ' +
      '중...',
    replyConfirmRequired:
      '에이전트 메시지 \u2014 고객 ' +
      '확인 필요',
    replyAwaitingOrder:
      '에이전트 메시지 \u2014 주문 ' +
      '또는 환불 요청 대기 중',
    replyOrderList:
      '에이전트 메시지 \u2014 고객 ' +
      '주문 내역',
    replyOrderInfo:
      '에이전트 메시지 \u2014 주문 ' +
      '상태 및 상세 정보',
    replyPolicyInfo:
      '에이전트 메시지 \u2014 반품 ' +
      '정책 및 지원 안내',
    replyDefault: '에이전트 메시지',
    confirmBtnPrefix: '환불 확정:',
    cancelBtnLabel: '아니요, 다른 주문 선택',
    requestRefundBtnPrefix: '환불 요청:',
    confirmPromptTemplate: (oid) =>
      `네, 주문 ORD-${oid} 환불을 ` +
      '확정합니다.',
    cancelPromptText:
      '아니요, 다른 주문을 ' +
      '환불하겠습니다.',
    requestRefundPromptTemplate: (oid) =>
      `주문 ORD-${oid} 환불을 ` +
      '요청합니다.',
    resetConfirmBadge: '데모 초기화 확인',
    resetConfirmHeading:
      '모든 데모 데이터를 ' +
      '초기화하시겠습니까?',
    resetConfirmDescHtml:
      'Cloud Spanner 데모 주문 ' +
      '(<code class="font-mono font-semibold">ORD-90124</code>, ' +
      '<code class="font-mono font-semibold">ORD-90125</code>, ' +
      '<code class="font-mono font-semibold">ORD-90126</code>, ' +
      '<code class="font-mono font-semibold">ORD-90588</code>, ' +
      '<code class="font-mono font-semibold">ORD-90910</code>)을 ' +
      '원래 상태로 복원하고, 30일 ' +
      '배송 및 100일 반품 기준 시각' +
      '을 현재 UTC 시각으로 갱신하' +
      '며, BigQuery <code class="font-mono font-semibold">' +
      'soa_action_lineage</code> 감사 트레이스를 ' +
      '모두 삭제합니다.',
    resetCancelBtn: '취소',
    resetConfirmBtn:
      '네, 데모 데이터 초기화',
    langSwitchBadge:
      '언어 변경 및 데모 데이터 ' +
      '초기화',
    langSwitchHeading:
      'UI 언어를 영어 (English)로 변경하' +
      '고 데모 데이터를 초기화하' +
      '시겠습니까?',
    langSwitchDescHtml:
      '언어를 변경하면 <strong>데모 ' +
      '데이터셋이 초기화</strong>되어' +
      ' Cloud Spanner 주문 상태, 채팅 내역 ' +
      '및 BigQuery <code class="font-mono font-semibold">' +
      'soa_action_lineage</code> 리니지 트레이스' +
      '가 새로운 언어 세션에 맞게' +
      ' 리셋됩니다.<br><span class="text-slate-500">' +
      '(Changing the language resets Cloud Spanner orders, chat history, and ' +
      'BigQuery lineage traces.)</span>',
    langSwitchConfirmBtn:
      '영어로 전환 및 데모 초기화' +
      ' (Switch to English)',
    resetRunningBadge:
      '듀얼 그래프 데모 초기화',
    resetRunningTitle:
      'Cloud Spanner & BigQuery 데모 상태 초기화' +
      ' 중...',
    resetRunningPrep:
      'Dual-Graph System of Action 초기화 시퀀스 ' +
      '준비 중...',
  },
};

const PROMPT_CHIPS_BY_USER = {
  1001: [
    {
      label: 'Request refund for ORD-90124 (Eligible Standard)',
      labelKo: 'ORD-90124 환불 요청 (적격 Standard)',
      prompt: 'I would like to request a refund for order ORD-90124.',
      promptKo: '주문 ORD-90124 환불을 ' +
        '요청합니다.',
    },
    {
      label: 'Request refund for ORD-90125 (Expired 45d > 30d)',
      labelKo: 'ORD-90125 환불 요청 (기한 만료' +
        ' 45일 > 30일)',
      prompt: 'Can I return and refund my order ORD-90125?',
      promptKo: '주문 ORD-90125 반품 및 환불이' +
        ' 가능한가요?',
    },
    {
      label: 'Request refund for ORD-90126 (Shipped / Not Delivered)',
      labelKo: 'ORD-90126 환불 요청 (배송 중 / ' +
        '미배달)',
      prompt: 'Please refund order ORD-90126.',
      promptKo: '주문 ORD-90126 환불해 주세요.',
    },
    {
      label: 'Can I refund my last order? (Auto-Infer ORD-90124)',
      labelKo: '가장 최근 주문 환불 (자' +
        '동 추론 ORD-90124)',
      prompt: 'Can I refund my last order?',
      promptKo: '가장 최근 주문을 환불' +
        '해 주세요.',
    },
  ],
  2048: [
    {
      label: 'Request refund for ORD-90588 (Standard 12 >= 10 Limit)',
      labelKo: 'ORD-90588 환불 요청 (Standard 12 >= 10 ' +
        '한도 초과)',
      prompt: 'Please refund my order ORD-90588.',
      promptKo: '주문 ORD-90588 환불을 ' +
        '요청합니다.',
    },
  ],
  3072: [
    {
      label: 'Request refund for ORD-90910 (VIP 12 < 20 Limit)',
      labelKo: 'ORD-90910 환불 요청 (VIP 12 < 20 한도' +
        ' 이내)',
      prompt: 'I would like to refund my order ORD-90910.',
      promptKo: '주문 ORD-90910 환불을 ' +
        '요청합니다.',
    },
  ],
};

const RESET_STAGES_BY_LANG = {
  en: [
    {
      pct: 25,
      title: 'Step 1/4: Clearing ADK 2.0 Session & Confirmation State',
      detail:
        'Resetting RefundSystemOfActionWorkflow pending customer ' +
        'confirmations and active session memory...',
    },
    {
      pct: 55,
      title: 'Step 2/4: Restoring Cloud Spanner OperationalContextGraph',
      detail:
        'Restoring orders ORD-90124, ORD-90588, and ORD-90910 to ' +
        'status="Complete", refreshing all 30-day delivery and 100-day ' +
        'return timestamps to current UTC time, and clearing ' +
        'refund_trace_id...',
    },
    {
      pct: 85,
      title: 'Step 3/4: Purging BigQuery ActionLineageGraph Audit Tables',
      detail:
        'Truncating soa_action_lineage.agent_sessions, workflow_nodes, ' +
        'policy_evaluations, and agent_actions in BigQuery...',
    },
    {
      pct: 100,
      title: 'Step 4/4: Reloading Live Customer Personas & Order Cards',
      detail:
        'Refreshing Cloud Spanner 100-day return counters, order statuses, ' +
        'and resetting support chat history \u2014 Demo reset complete!',
    },
  ],
  ko: [
    {
      pct: 25,
      title:
        '1/4단계: ADK 2.0 세션 및 고객 확인' +
        ' 상태 초기화',
      detail:
        'RefundSystemOfActionWorkflow의 대기 중인 ' +
        '고객 확인 및 세션 메모리를' +
        ' 초기화하는 중...',
    },
    {
      pct: 55,
      title: '2/4단계: Cloud Spanner OperationalContextGraph 복원',
      detail:
        'ORD-90124, ORD-90588, ORD-90910 주문을 ' +
        'status="Complete"로 복원하고, 30일 배송' +
        ' 및 100일 반품 타임스탬프를 ' +
        '현재 UTC 시각으로 갱신 중...',
    },
    {
      pct: 85,
      title:
        '3/4단계: BigQuery ActionLineageGraph 감사 ' +
        '테이블 비우기',
      detail:
        'BigQuery의 soa_action_lineage.agent_sessions, workflow_nodes, ' +
        'policy_evaluations, agent_actions 테이블을 ' +
        '초기화하는 중...',
    },
    {
      pct: 100,
      title:
        '4/4단계: 실시간 고객 페르소' +
        '나 및 주문 카드 새로고침',
      detail:
        'Cloud Spanner 100일 반품 카운터, 주문' +
        ' 상태 및 채팅 내역 새로고침' +
        ' \u2014 데모 초기화 완료!',
    },
  ],
};

let currentLang = 'en';
try {
  if (window.localStorage.getItem(LANG_STORAGE_KEY) === 'ko') {
    currentLang = 'ko';
  }
} catch {
  currentLang = 'en';
}

let pendingLanguageTarget = null;
let activeUserId = 1001;
let customersCache = [];
let pendingOrderByUser = {};
let chatHistoryByUser = {};
let isChatRequestInFlight = false;
let agentLoadingTimerId = null;

function loadPersistedChatState() {
  try {
    const savedUserId = Number(
        window.localStorage.getItem(ACTIVE_USER_STORAGE_KEY),
    );
    if ([1001, 2048, 3072].includes(savedUserId)) {
      activeUserId = savedUserId;
    }
    const rawHistory = window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
    if (rawHistory) {
      const parsedHistory = JSON.parse(rawHistory);
      if (parsedHistory && typeof parsedHistory === 'object') {
        chatHistoryByUser = parsedHistory;
      }
    }
    const rawPending = window.localStorage.getItem(PENDING_ORDER_STORAGE_KEY);
    if (rawPending) {
      const parsedPending = JSON.parse(rawPending);
      if (parsedPending && typeof parsedPending === 'object') {
        pendingOrderByUser = parsedPending;
      }
    }
  } catch {
    // Ignore storage or JSON errors in restricted browsing contexts
  }
}

function savePersistedChatState() {
  try {
    window.localStorage.setItem(
        ACTIVE_USER_STORAGE_KEY,
        String(activeUserId),
    );
    window.localStorage.setItem(
        CHAT_HISTORY_STORAGE_KEY,
        JSON.stringify(chatHistoryByUser),
    );
    window.localStorage.setItem(
        PENDING_ORDER_STORAGE_KEY,
        JSON.stringify(pendingOrderByUser),
    );
  } catch {
    // Ignore storage quota or private browsing errors
  }
}

function clearPersistedChatState() {
  try {
    window.localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
    window.localStorage.removeItem(PENDING_ORDER_STORAGE_KEY);
    window.localStorage.removeItem(ACTIVE_USER_STORAGE_KEY);
  } catch {
    // Ignore storage errors in private browsing mode
  }
}

function buildLoadingSteps(userId) {
  if (currentLang === 'ko') {
    return [
      '[1/5] IntentAgent: gemini-3-flash-preview로 고객 의도 및' +
        ' 대상 주문 분석 중...',
      '[2/5] Knowledge Catalog: customer-loyalty-tier 및' +
        ' 100일 반품 지표 계약 조회 중...',
      `[3/5] Spanner Graph: 고객 ${userId}의 ` +
        'OperationalContextGraph ISO GQL 탐색 중...',
      '[4/5] Action Router: 2단계 확인 게이트 검증 및' +
        ' BigQuery ActionLineageGraph 기록 중...',
      '[5/5] ResponseAgent: gemini-3-flash-preview로 정책 검증' +
        ' 기반 응답 생성 중...',
    ];
  }
  return [
    '[1/5] IntentAgent: Resolving intent & target order with ' +
      'gemini-3-flash-preview...',
    '[2/5] Knowledge Catalog: Fetching customer-loyalty-tier & ' +
      '100d metric contracts...',
    '[3/5] Spanner Graph: Executing ISO GQL on OperationalContextGraph ' +
      `(user_id=${userId})...`,
    '[4/5] Action Router: Checking 2-turn confirmation gate & streaming ' +
      'BigQuery ActionLineageGraph...',
    '[5/5] ResponseAgent: Synthesizing grounded response with ' +
      'gemini-3-flash-preview...',
  ];
}

function t() {
  return SHOP_I18N[currentLang] || SHOP_I18N.en;
}

function escapeHtml(value) {
  return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll('\'', '&#39;');
}

function setTextById(id, text) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = text;
  }
}

function applyShopLanguage() {
  const strings = t();
  document.documentElement.lang = currentLang;
  document.title = strings.pageTitle;
  setTextById('shop-header-title', strings.headerTitle);
  setTextById('shop-header-subtitle', strings.headerSubtitle);
  setTextById('nav-shop-link', strings.navShop);
  setTextById('nav-console-link', strings.navConsole);
  setTextById('reset-demo-btn', strings.resetBtnText);
  setTextById('shop-sec1-title', strings.sec1Title);
  setTextById('shop-sec1-subtitle', strings.sec1Subtitle);
  setTextById('shop-sec2-title', strings.sec2Title);
  setTextById('shop-sec3-title', strings.sec3Title);
  setTextById('shop-sec3-subtitle', strings.sec3Subtitle);
  setTextById('shop-chat-title', strings.chatTitle);
  setTextById('shop-chat-subtitle', strings.chatSubtitle);
  setTextById('clear-chat-label', strings.clearChatLabel);
  setTextById('prompt-chips-heading', strings.promptChipsHeading);

  const langBtn = document.getElementById('lang-toggle-btn');
  if (langBtn) {
    langBtn.textContent = strings.langBtnText;
    langBtn.title = strings.langBtnTitle;
  }
  const clearBtn = document.getElementById('clear-chat-btn');
  if (clearBtn) {
    clearBtn.title = strings.clearChatTitle;
  }
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.placeholder = strings.chatInputPlaceholder;
  }
  if (!isChatRequestInFlight) {
    setTextById('chat-submit-btn', strings.sendBtn);
  }
}

function getProductPhotoUrl(productName) {
  const lower = String(productName || '').toLowerCase();
  if (lower.includes('jacket') || lower.includes('shell')) {
    return '/static/products/jacket.png';
  }
  if (lower.includes('pullover') || lower.includes('sweater')) {
    return '/static/products/pullover.png';
  }
  if (lower.includes('shoe') || lower.includes('running')) {
    return '/static/products/shoes.png';
  }
  if (lower.includes('jeans') || lower.includes('denim')) {
    return '/static/products/jeans.png';
  }
  if (lower.includes('sunglasses') || lower.includes('aviator')) {
    return '/static/products/sunglasses.png';
  }
  if (lower.includes('shirt') || lower.includes('oxford')) {
    return '/static/products/shirt.png';
  }
  if (lower.includes('blazer') || lower.includes('suit')) {
    return '/static/products/blazer.png';
  }
  if (lower.includes('beanie') || lower.includes('cashmere')) {
    return '/static/products/beanie.png';
  }
  return '/static/products/jacket.png';
}

function renderPersonaCards() {
  const container = document.getElementById('persona-cards');
  if (!container) return;
  const strings = t();
  container.innerHTML = customersCache
      .map((cust) => {
        const isSelected = cust.user_id === activeUserId;
        const borderClass = isSelected ?
        'border-blue-500 bg-blue-50/80 dark:bg-blue-950/40' :
        'border-slate-200 bg-slate-50 hover:border-slate-300 ' +
          'dark:border-slate-800 dark:bg-slate-950/60 ' +
          'dark:hover:border-slate-700';
        const tierBadge =
        cust.customer_tier === 'VIP' ?
          'bg-purple-100 text-purple-800 border border-purple-300 ' +
            'dark:bg-purple-900/80 dark:text-purple-200 ' +
            'dark:border-purple-600' :
          'bg-slate-200 text-slate-700 border border-slate-300 ' +
            'dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700';
        const fullName =
        `${escapeHtml(cust.first_name)} ${escapeHtml(cust.last_name)}`;
        const returnRatio =
        `${cust.prior_refund_count_100d} / ${cust.max_refunds_100d}`;
        return [
          '<button type="button"',
          ` data-user-id="${cust.user_id}"`,
          ' class="persona-btn text-left p-3.5 rounded-lg border transition',
          ` ${borderClass}">`,
          '<div class="flex items-center justify-between gap-2">',
          '<span class="font-semibold text-sm text-slate-900 dark:text-white">',
          `${fullName}</span>`,
          '<span class="text-[11px] px-2 py-0.5 rounded font-mono',
          ` ${tierBadge}">${escapeHtml(cust.customer_tier)}</span>`,
          '</div>',
          '<p class="text-xs text-slate-500 dark:text-slate-400 mt-1',
          ` truncate">${escapeHtml(cust.email)} (ID: ${cust.user_id})</p>`,
          '<p class="text-xs text-slate-700 dark:text-slate-300 mt-2',
          ` font-mono">${escapeHtml(strings.returns100dLabel)} `,
          `${returnRatio}</p>`,
          '</button>',
        ].join('');
      })
      .join('');

  container.querySelectorAll('.persona-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeUserId = Number(btn.getAttribute('data-user-id'));
      savePersistedChatState();
      renderPersonaCards();
      renderPromptChips();
      loadCustomerOrders(activeUserId);
      renderChatMessages(activeUserId);
    });
  });
}

function renderPromptChips() {
  const chipsContainer = document.getElementById('prompt-chips');
  if (!chipsContainer) return;
  const chips = PROMPT_CHIPS_BY_USER[activeUserId] || [];
  const isKo = currentLang === 'ko';
  chipsContainer.innerHTML = chips
      .map((chip) => {
        const chipPrompt = isKo ? chip.promptKo : chip.prompt;
        const chipLabel = isKo ? chip.labelKo : chip.label;
        return [
          '<button type="button"',
          ` data-prompt="${escapeHtml(chipPrompt)}"`,
          ' class="prompt-chip text-xs px-2.5 py-1.5 rounded-md bg-blue-50',
          ' hover:bg-blue-100 text-blue-700 border border-blue-200',
          ' dark:bg-slate-800 dark:hover:bg-blue-900/60 dark:text-blue-200',
          ' dark:border-slate-700">',
          escapeHtml(chipLabel),
          '</button>',
        ].join('');
      })
      .join('');

  chipsContainer.querySelectorAll('.prompt-chip').forEach((btn) => {
    btn.addEventListener('click', () => {
      const promptText = btn.getAttribute('data-prompt') || '';
      submitRefundPrompt(promptText);
    });
  });
}

async function loadCustomerOrders(userId) {
  const badge = document.getElementById('active-persona-badge');
  const activeCustomer = customersCache.find((c) => c.user_id === userId);
  if (badge && activeCustomer) {
    badge.textContent =
      `user_id: ${userId} | tier: ${activeCustomer.customer_tier}`;
  }
  const container = document.getElementById('orders-container');
  if (!container) return;
  const strings = t();
  const response = await fetch(`/api/customers/${userId}/orders`);
  const data = await response.json();
  const orders = (data.orders || []).slice(0, 6);
  container.innerHTML = orders
      .map((order) => {
        const statusColor =
        order.status === 'Returned' ?
          'bg-amber-100 text-amber-800 border-amber-300 ' +
            'dark:bg-amber-900/60 dark:text-amber-200 dark:border-amber-700' :
          order.status === 'Complete' ?
            'bg-emerald-100 text-emerald-800 border-emerald-300 ' +
              'dark:bg-emerald-900/60 dark:text-emerald-200 ' +
              'dark:border-emerald-700' :
            'bg-slate-200 text-slate-700 border-slate-300 ' +
              'dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
        const itemsHtml = (order.items || [])
            .map((item) => {
              const priceStr = Number(item.sale_price).toFixed(2);
              const traceLabel = item.refund_trace_id ?
            `trace: ${escapeHtml(item.refund_trace_id)}` :
            escapeHtml(item.status);
              const photoUrl = getProductPhotoUrl(item.product_name);
              const itemAlt = escapeHtml(item.product_name);
              return [
                '<div class="flex items-center justify-between gap-3 text-xs',
                ' text-slate-700 dark:text-slate-300 py-1.5 border-t',
                ' border-slate-200 dark:border-slate-800/70">',
                '<div class="flex items-center gap-2.5 min-w-0">',
                `<img src="${photoUrl}" alt="${itemAlt}" loading="lazy"`,
                ' class="order-item-photo w-11 h-11 rounded-md object-cover',
                ' border border-slate-200 bg-white shrink-0">',
                '<div class="min-w-0">',
                '<div class="font-medium text-slate-900 dark:text-white',
                ` truncate">${itemAlt}</div>`,
                '<div class="text-[11px] font-semibold text-emerald-700',
                ` dark:text-emerald-300">$${priceStr}</div>`,
                '</div>',
                '</div>',
                '<span class="font-mono text-[11px] text-slate-500',
                ` dark:text-slate-400 shrink-0">${traceLabel}</span>`,
                '</div>',
              ].join('');
            })
            .join('');
        const deliveredText = escapeHtml(
            order.delivered_at || strings.inTransitText,
        );
        return [
          '<div class="p-3 rounded-lg bg-slate-50 border border-slate-200',
          ' dark:bg-slate-950/70 dark:border-slate-800">',
          '<div class="flex items-center justify-between mb-1.5">',
          '<span class="font-mono text-sm font-semibold text-slate-900',
          ` dark:text-white">ORD-${order.order_id}</span>`,
          `<span class="text-xs px-2 py-0.5 rounded border ${statusColor}">`,
          `${escapeHtml(order.status)}</span>`,
          '</div>',
          '<div class="text-[11px] text-slate-500 dark:text-slate-400 mb-2">',
          `${escapeHtml(strings.deliveredLabel)} ${deliveredText}</div>`,
          itemsHtml,
          '</div>',
        ].join('');
      })
      .join('');
}

async function loadProducts() {
  const grid = document.getElementById('products-grid');
  if (!grid) return;
  const strings = t();
  const response = await fetch('/api/products');
  const data = await response.json();
  const products = data.products || [];
  grid.innerHTML = products
      .map((prod) => {
        const priceStr = Number(prod.retail_price).toFixed(2);
        const photoUrl = getProductPhotoUrl(prod.name);
        const prodAlt = escapeHtml(prod.name);
        return [
          '<div class="p-3 rounded-lg bg-slate-50 border border-slate-200',
          ' dark:bg-slate-950/70 dark:border-slate-800 flex flex-col',
          ' justify-between gap-2.5">',
          '<div class="flex items-start gap-3">',
          `<img src="${photoUrl}" alt="${prodAlt}" loading="lazy"`,
          ' class="product-catalog-photo w-14 h-14 rounded-lg object-cover',
          ' border border-slate-200 bg-white shrink-0 shadow-xs">',
          '<div class="min-w-0 flex-1">',
          '<div class="flex items-center justify-between gap-2">',
          '<span class="text-xs font-mono text-blue-700 dark:text-blue-400">',
          `#${prod.id} ${escapeHtml(prod.brand)}</span>`,
          '<span class="text-xs font-semibold text-emerald-700',
          ` dark:text-emerald-300 shrink-0">$${priceStr}</span>`,
          '</div>',
          '<p class="text-sm font-medium text-slate-900 dark:text-white',
          ` mt-1 leading-snug">${prodAlt}</p>`,
          '</div>',
          '</div>',
          '<div class="pt-2 border-t border-slate-200',
          ' dark:border-slate-800/80 flex items-center justify-between',
          ' text-[11px] text-slate-500 dark:text-slate-400">',
          `<span>${escapeHtml(strings.dcPrefix)} `,
          `${escapeHtml(prod.distribution_center_name)}</span>`,
          `<span class="font-mono">${escapeHtml(prod.policy_id)}</span>`,
          '</div>',
          '</div>',
        ].join('');
      })
      .join('');
}

function createChatMessageElement(role, htmlContent) {
  const wrapper = document.createElement('div');
  wrapper.className =
    role === 'user' ?
      'ml-8 p-3 rounded-lg bg-blue-50 border border-blue-200 ' +
        'dark:bg-blue-950/70 dark:border-blue-800 text-xs' :
      'mr-4 p-3 rounded-lg bg-white border border-slate-200 shadow-sm ' +
        'dark:bg-slate-900 dark:border-slate-700 text-xs space-y-2';
  wrapper.innerHTML = htmlContent;
  wrapper.querySelectorAll('.candidate-order-chip').forEach((btn) => {
    btn.addEventListener('click', () => {
      const promptText = btn.getAttribute('data-prompt') || '';
      submitRefundPrompt(promptText, false);
    });
  });
  wrapper.querySelectorAll('.confirm-refund-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const promptText = btn.getAttribute('data-prompt') || '';
      submitRefundPrompt(promptText, true);
    });
  });
  wrapper.querySelectorAll('.cancel-refund-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const promptText = btn.getAttribute('data-prompt') || '';
      submitRefundPrompt(promptText, false);
    });
  });
  return wrapper;
}

function buildEmptyChatBannerHtml(userId) {
  const strings = t();
  const cust = customersCache.find((c) => c.user_id === userId);
  const fullName = cust ?
    escapeHtml(`${cust.first_name} ${cust.last_name}`) :
    `${escapeHtml(strings.customerPrefix)} ${userId}`;
  const tier = cust ? escapeHtml(cust.customer_tier) : 'STANDARD';
  if (currentLang === 'ko') {
    return [
      '<div class="text-xs text-slate-600 bg-white border border-slate-200',
      ' dark:text-slate-400 dark:bg-slate-900 dark:border-slate-800',
      ' rounded-lg p-3">',
      '<div class="font-semibold text-slate-800 dark:text-slate-200 mb-1">',
      `활성 채팅 세션: ${fullName}`,
      ` (ID: ${userId} &middot; ${tier})</div>`,
      '위의 프롬프트 칩을 클릭하' +
        '거나 자연어로 환불을 요청' +
        '하세요 (예: ',
      '<code class="text-blue-700 dark:text-blue-300 font-semibold">',
      'ORD-90124</code>, <code class="text-blue-700 dark:text-blue-300',
      ' font-semibold">ORD-90588</code>, <code class="text-blue-700',
      ' dark:text-blue-300 font-semibold">ORD-90910</code>) \u2014 5단계',
      ' ADK 2.0 환불 워크플로가 실행됩' +
        '니다.',
      '</div>',
    ].join('');
  }
  return [
    '<div class="text-xs text-slate-600 bg-white border border-slate-200',
    ' dark:text-slate-400 dark:bg-slate-900 dark:border-slate-800',
    ' rounded-lg p-3">',
    `<div class="font-semibold text-slate-800 dark:text-slate-200 mb-1">`,
    `Active Chat Session: ${fullName} (ID: ${userId} &middot; ${tier})</div>`,
    'Click a prompt chip above or type a natural-language refund request',
    ' (such as <code class="text-blue-700 dark:text-blue-300 font-semibold">',
    'ORD-90124</code>, <code class="text-blue-700 dark:text-blue-300',
    ' font-semibold">ORD-90588</code>, or <code class="text-blue-700',
    ' dark:text-blue-300 font-semibold">ORD-90910</code>) to run the 5-step',
    ' ADK 2.0 refund workflow.',
    '</div>',
  ].join('');
}

function updateChatPersonaHeader(userId) {
  const labelEl = document.getElementById('chat-persona-label');
  if (!labelEl) return;
  const strings = t();
  const cust = customersCache.find((c) => c.user_id === userId);
  if (cust) {
    labelEl.textContent =
      `${cust.first_name} ${cust.last_name}` +
      ` (${userId} \u00b7 ${cust.customer_tier})`;
  } else {
    labelEl.textContent = `${strings.customerPrefix} (${userId})`;
  }
}

function renderChatMessages(userId = activeUserId) {
  updateChatPersonaHeader(userId);
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const history = chatHistoryByUser[userId] || [];
  container.innerHTML = '';
  if (history.length === 0) {
    container.innerHTML = buildEmptyChatBannerHtml(userId);
    return;
  }
  history.forEach((entry) => {
    const wrapper = createChatMessageElement(entry.role, entry.htmlContent);
    container.appendChild(wrapper);
  });
  container.scrollTop = container.scrollHeight;
}

function clearActivePersonaChat() {
  delete chatHistoryByUser[activeUserId];
  delete pendingOrderByUser[activeUserId];
  savePersistedChatState();
  renderChatMessages(activeUserId);
}

function appendChatMessage(role, htmlContent, userId = activeUserId) {
  if (!chatHistoryByUser[userId]) {
    chatHistoryByUser[userId] = [];
  }
  const hadMessages = chatHistoryByUser[userId].length > 0;
  chatHistoryByUser[userId].push({role, htmlContent});
  savePersistedChatState();
  if (userId !== activeUserId) {
    return;
  }
  const container = document.getElementById('chat-messages');
  if (!container) return;
  if (!hadMessages) {
    container.innerHTML = '';
  }
  const wrapper = createChatMessageElement(role, htmlContent);
  container.appendChild(wrapper);
  container.scrollTop = container.scrollHeight;
}

const SPINNER_SVG = [
  '<svg class="animate-spin h-4 w-4 text-blue-600 shrink-0"',
  ' xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"',
  ' aria-hidden="true">',
  '<circle class="opacity-25" cx="12" cy="12" r="10"',
  ' stroke="currentColor" stroke-width="4"></circle>',
  '<path class="opacity-75" fill="currentColor"',
  ' d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>',
  '</svg>',
].join('');

function setChatLoadingState(isLoading) {
  const strings = t();
  const chatInput = document.getElementById('chat-input');
  const submitBtn = document.getElementById('chat-submit-btn');
  if (chatInput) {
    chatInput.disabled = isLoading;
    if (!isLoading) {
      chatInput.focus({preventScroll: true});
    }
  }
  if (submitBtn) {
    submitBtn.disabled = isLoading;
    if (isLoading) {
      submitBtn.classList.add('opacity-75', 'cursor-wait');
      submitBtn.innerHTML = [
        '<span class="inline-flex items-center gap-1.5">',
        '<svg class="animate-spin h-3.5 w-3.5 text-white"',
        ' xmlns="http://www.w3.org/2000/svg" fill="none"',
        ' viewBox="0 0 24 24" aria-hidden="true">',
        '<circle class="opacity-25" cx="12" cy="12" r="10"',
        ' stroke="currentColor" stroke-width="4"></circle>',
        '<path class="opacity-75" fill="currentColor"',
        ' d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>',
        '</svg>',
        `<span>${escapeHtml(strings.runningBtn)}</span>`,
        '</span>',
      ].join('');
    } else {
      submitBtn.classList.remove('opacity-75', 'cursor-wait');
      submitBtn.textContent = strings.sendBtn;
    }
  }
}

function showAgentLoadingIndicator() {
  removeAgentLoadingIndicator();
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const strings = t();
  const steps = buildLoadingSteps(activeUserId);
  const loadingEl = document.createElement('div');
  loadingEl.id = 'agent-loading-indicator';
  loadingEl.setAttribute('role', 'status');
  loadingEl.setAttribute('aria-live', 'polite');
  loadingEl.className =
    'mr-4 p-3 rounded-lg bg-white border border-blue-200 shadow-sm ' +
    'dark:bg-slate-900 dark:border-blue-800 text-xs space-y-2';
  loadingEl.innerHTML = [
    '<div class="flex items-center justify-between gap-2">',
    '<span class="font-semibold text-slate-900 dark:text-white">',
    'ADK 2.0 RefundSystemOfActionWorkflow</span>',
    '<span id="agent-loading-step-badge"',
    ' class="px-2 py-0.5 rounded border font-mono text-[11px]',
    ' bg-blue-50 text-blue-700 border-blue-200 animate-pulse">',
    'STEP 1/5</span>',
    '</div>',
    '<div class="flex items-center gap-2.5 p-2.5 rounded-lg bg-blue-50/70',
    ' border border-blue-200/80 text-slate-700 dark:bg-blue-950/40',
    ' dark:border-blue-800 dark:text-slate-200">',
    SPINNER_SVG,
    '<div class="min-w-0 flex-1 space-y-0.5">',
    '<div class="font-semibold text-blue-900 dark:text-blue-200">',
    `${escapeHtml(strings.loadingTitle)}</div>`,
    '<div id="agent-loading-step-text"',
    ' class="agent-step-ticker font-mono text-[11px] text-blue-700',
    ' dark:text-blue-300 whitespace-nowrap overflow-hidden text-ellipsis">',
    `${escapeHtml(steps[0])}</div>`,
    '</div>',
    '</div>',
  ].join('');
  container.appendChild(loadingEl);
  container.scrollTop = container.scrollHeight;
}

function updateAgentLoadingStep(stepEvent) {
  const stepEl = document.getElementById('agent-loading-step-text');
  const badgeEl = document.getElementById('agent-loading-step-badge');
  const idx = Number(stepEvent.step_index || 1);
  const total = Number(stepEvent.total_steps || 5);
  const detail =
    currentLang === 'ko' ?
      stepEvent.detail_ko || stepEvent.detail_en :
      stepEvent.detail_en || stepEvent.detail_ko;
  if (badgeEl) {
    badgeEl.textContent = `STEP ${idx}/${total}`;
  }
  if (stepEl && detail) {
    stepEl.classList.remove('agent-step-ticker');
    void stepEl.offsetWidth;
    stepEl.textContent = detail;
    stepEl.classList.add('agent-step-ticker');
  }
}

async function consumeRefundStream(response) {
  if (!response.body || typeof response.body.getReader !== 'function') {
    const rawBody = await response.text();
    let parsed = {};
    try {
      parsed = JSON.parse(rawBody);
    } catch {
      parsed = {detail: rawBody.slice(0, 160).trim() || response.statusText};
    }
    return {ok: response.ok, result: parsed};
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;
  let errorDetail = null;

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const rawLine of lines) {
      const trimmedLine = rawLine.trim();
      if (!trimmedLine) continue;
      let eventObj = null;
      try {
        eventObj = JSON.parse(trimmedLine);
      } catch {
        continue;
      }
      if (eventObj.type === 'step') {
        updateAgentLoadingStep(eventObj);
        if (
          eventObj.phase === 'start' ||
          eventObj.node_name === 'evaluate_spanner_policy'
        ) {
          await delayMs(160);
        }
      } else if (eventObj.type === 'result') {
        finalResult = eventObj.data || {};
      } else if (eventObj.type === 'error') {
        errorDetail = eventObj.detail || 'Refund workflow request failed.';
      }
    }
  }
  if (errorDetail) {
    return {ok: false, result: {detail: errorDetail}};
  }
  if (finalResult) {
    return {ok: true, result: finalResult};
  }
  return {
    ok: false,
    result: {detail: `HTTP ${response.status}: ${response.statusText}`},
  };
}

function removeAgentLoadingIndicator() {
  if (agentLoadingTimerId !== null) {
    window.clearInterval(agentLoadingTimerId);
    agentLoadingTimerId = null;
  }
  const existing = document.getElementById('agent-loading-indicator');
  if (existing) {
    existing.remove();
  }
}

async function submitRefundPrompt(messageText, confirmed = false) {
  const trimmed = messageText.trim();
  if (!trimmed || isChatRequestInFlight) return;
  const strings = t();
  const requestUserId = activeUserId;
  isChatRequestInFlight = true;
  appendChatMessage(
      'user',
      [
        '<div class="font-semibold text-blue-700 dark:text-blue-300 mb-1">',
        `${escapeHtml(strings.customerPrefix)} (${requestUserId})</div>`,
        '<div class="text-slate-800 dark:text-slate-100">',
        `${escapeHtml(trimmed)}</div>`,
      ].join(''),
      requestUserId,
  );
  setChatLoadingState(true);
  showAgentLoadingIndicator();

  let streamOutcome = {ok: false, result: {}};
  let result = {};
  try {
    const currentPending = pendingOrderByUser[requestUserId] || null;
    const response = await fetch('/api/chat/refund/stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        user_id: requestUserId,
        message: trimmed,
        confirmed: Boolean(confirmed),
        pending_order_id: currentPending ? currentPending.order_id : null,
      }),
    });
    if (!response.ok) {
      const rawBody = await response.text();
      streamOutcome = {
        ok: false,
        result: {
          detail:
            `HTTP ${response.status}: ` +
            `${rawBody.slice(0, 160).trim() || response.statusText}`,
        },
      };
    } else {
      streamOutcome = await consumeRefundStream(response);
    }
    result = streamOutcome.result || {};
  } catch (err) {
    removeAgentLoadingIndicator();
    setChatLoadingState(false);
    isChatRequestInFlight = false;
    appendChatMessage(
        'agent',
        [
          '<div class="font-semibold text-rose-700 dark:text-rose-300">',
          'ADK 2.0 RefundSystemOfActionWorkflow Error</div>',
          '<p class="text-rose-600 dark:text-rose-200 font-mono text-xs">',
          `${escapeHtml(err.message || 'Network request failed.')}`,
          '</p>',
        ].join(''),
        requestUserId,
    );
    return;
  } finally {
    removeAgentLoadingIndicator();
    setChatLoadingState(false);
    isChatRequestInFlight = false;
  }

  if (!streamOutcome.ok) {
    appendChatMessage(
        'agent',
        [
          '<div class="font-semibold text-rose-700 dark:text-rose-300">',
          'ADK 2.0 RefundSystemOfActionWorkflow Error</div>',
          '<p class="text-rose-600 dark:text-rose-200 font-mono text-xs">',
          `${escapeHtml(result.detail || 'Refund workflow request failed.')}`,
          '</p>',
        ].join(''),
        requestUserId,
    );
    return;
  }
  const isApproved = result.decision_status === 'APPROVED';
  const isPending = result.decision_status === 'PENDING_CONFIRMATION';
  const isOrderList = result.decision_status === 'ORDER_LIST';
  const isOrderInfo = result.decision_status === 'ORDER_INFO';
  const isPolicyInfo = result.decision_status === 'POLICY_INFO';
  const isInfo = isOrderList || isOrderInfo || isPolicyInfo;
  if (isPending && result.pending_confirmation) {
    pendingOrderByUser[requestUserId] = result.pending_confirmation;
  } else {
    delete pendingOrderByUser[requestUserId];
  }
  const badgeClass = isApproved ?
    'bg-emerald-100 text-emerald-800 border-emerald-300 ' +
      'dark:bg-emerald-900/80 dark:text-emerald-200 dark:border-emerald-600' :
    isPending ?
      'bg-amber-100 text-amber-800 border-amber-300 ' +
        'dark:bg-amber-900/80 dark:text-amber-200 dark:border-amber-600' :
      isInfo ?
        'bg-blue-100 text-blue-800 border-blue-300 ' +
          'dark:bg-blue-900/80 dark:text-blue-200 dark:border-blue-600' :
        'bg-rose-100 text-rose-800 border-rose-300 ' +
          'dark:bg-rose-900/80 dark:text-rose-200 dark:border-rose-600';
  const replyCalloutClass = isApproved ?
    'bg-emerald-50 border border-emerald-300 border-l-4 ' +
      'border-l-emerald-500 text-slate-900 dark:bg-emerald-950/50 ' +
      'dark:border-emerald-700 dark:border-l-emerald-400 dark:text-emerald-50' :
    isPending ?
      'bg-amber-50 border border-amber-300 border-l-4 ' +
        'border-l-amber-500 text-slate-900 dark:bg-amber-950/50 ' +
        'dark:border-amber-700 dark:border-l-amber-400 dark:text-amber-50' :
      isInfo ?
        'bg-blue-50 border border-blue-300 border-l-4 ' +
          'border-l-blue-500 text-slate-900 dark:bg-blue-950/50 ' +
          'dark:border-blue-700 dark:border-l-blue-400 dark:text-blue-50' :
        'bg-rose-50 border border-rose-300 border-l-4 ' +
          'border-l-rose-500 text-slate-900 dark:bg-rose-950/50 ' +
          'dark:border-rose-700 dark:border-l-rose-400 dark:text-rose-50';
  const replyHeaderColor = isApproved ?
    'text-emerald-800 dark:text-emerald-300' :
    isPending ?
      'text-amber-800 dark:text-amber-300' :
      isInfo ?
        'text-blue-800 dark:text-blue-300' :
        'text-rose-800 dark:text-rose-300';
  const pe = result.policy_eval || {};
  const traceHref = `/console?trace_id=${encodeURIComponent(result.trace_id)}`;
  const pendingConf = result.pending_confirmation || {};
  const confirmOid = pendingConf.order_id || result.order_id;
  const hasOrderCard = Boolean(confirmOid && (isPending || pe.order_found));
  const replyHeaderText =
    isPending && confirmOid ?
      strings.replyConfirmRequired :
      isPending ?
        strings.replyAwaitingOrder :
        isOrderList ?
          strings.replyOrderList :
          isOrderInfo ?
            strings.replyOrderInfo :
            isPolicyInfo ?
              strings.replyPolicyInfo :
              strings.replyDefault;
  const rawConfirmProd =
    pendingConf.product_name || pe.product_names || 'Order Item';
  const confirmProd = escapeHtml(rawConfirmProd);
  const confirmPhotoUrl = getProductPhotoUrl(rawConfirmProd);
  const confirmPrice = Number(
      pendingConf.sale_price ?? pe.target_order_price ?? 0,
  ).toFixed(2);
  const rawOrderStatus = isApproved ?
    'Returned' :
    pendingConf.status || pe.target_order_status || 'Complete';
  const orderStatusText = escapeHtml(rawOrderStatus);
  const orderStatusBadge = rawOrderStatus === 'Returned' ?
    'bg-amber-100 text-amber-800 border-amber-300' :
    rawOrderStatus === 'Complete' ?
      'bg-emerald-100 text-emerald-800 border-emerald-300' :
      'bg-slate-200 text-slate-700 border-slate-300';
  const orderCardTone = isApproved ?
    'bg-emerald-50/70 border-emerald-200' :
    isPending ?
      'bg-amber-50/70 border-amber-200' :
      isInfo ?
        'bg-blue-50/70 border-blue-200' :
        'bg-rose-50/70 border-rose-200';
  const orderPhotoBorder = isApproved ?
    'border-emerald-300' :
    isPending ?
      'border-amber-300' :
      isInfo ?
        'border-blue-300' :
        'border-rose-300';
  const confirmPrompt = strings.confirmPromptTemplate(confirmOid);
  const cancelPrompt = strings.cancelPromptText;
  const requestRefundPrompt = strings.requestRefundPromptTemplate(confirmOid);
  const confirmActionsHtml = isPending ?
    [
      '<div class="flex flex-wrap gap-1.5 pt-1 border-t border-amber-200/80">',
      '<button type="button"',
      ` data-prompt="${escapeHtml(confirmPrompt)}"`,
      ' class="confirm-refund-btn text-xs px-3 py-1.5 rounded-md',
      ' bg-emerald-600 hover:bg-emerald-500 text-white border',
      ' border-emerald-700 font-semibold shadow-sm">',
      `${escapeHtml(strings.confirmBtnPrefix)} ORD-${confirmOid} &mdash; `,
      `${confirmProd} ($${confirmPrice})`,
      '</button>',
      '<button type="button"',
      ` data-prompt="${escapeHtml(cancelPrompt)}"`,
      ' class="cancel-refund-btn text-xs px-3 py-1.5 rounded-md',
      ' bg-white hover:bg-slate-100 text-slate-700 border',
      ' border-slate-300 font-medium">',
      `${escapeHtml(strings.cancelBtnLabel)}`,
      '</button>',
      '</div>',
    ].join('') :
    isOrderInfo ?
      [
        '<div class="flex flex-wrap gap-1.5 pt-1 border-t border-blue-200/80">',
        '<button type="button"',
        ` data-prompt="${escapeHtml(requestRefundPrompt)}"`,
        ' class="candidate-order-chip text-xs px-3 py-1.5 rounded-md',
        ' bg-blue-600 hover:bg-blue-500 text-white border',
        ' border-blue-700 font-semibold shadow-sm">',
        `${escapeHtml(strings.requestRefundBtnPrefix)} ORD-${confirmOid} `,
        `&mdash; ${confirmProd} ($${confirmPrice})`,
        '</button>',
        '</div>',
      ].join('') :
      '';
  const orderCardHtml = hasOrderCard ?
    [
      `<div class="chat-order-card p-3 rounded-lg border ${orderCardTone}`,
      ' space-y-2.5">',
      '<div class="flex items-center gap-3">',
      `<img src="${confirmPhotoUrl}" alt="${confirmProd}" loading="lazy"`,
      ' class="confirm-order-photo w-14 h-14 rounded-lg object-cover border',
      ` ${orderPhotoBorder} bg-white shrink-0 shadow-xs">`,
      '<div class="min-w-0 flex-1">',
      '<div class="flex items-center justify-between gap-2">',
      '<span class="font-mono text-xs font-bold text-slate-900">',
      `ORD-${confirmOid}</span>`,
      '<span class="text-[11px] px-2 py-0.5 rounded border font-medium',
      ` ${orderStatusBadge}">${orderStatusText}</span>`,
      '</div>',
      '<div class="text-xs font-semibold text-slate-900 truncate mt-0.5">',
      `${confirmProd}</div>`,
      '<div class="text-xs font-bold text-emerald-700 mt-0.5">',
      `${escapeHtml(strings.orderAmountPrefix)} $${confirmPrice}</div>`,
      '</div>',
      '</div>',
      confirmActionsHtml,
      '</div>',
    ].join('') :
    '';
  const showCandidates =
    (isOrderList ||
      isPolicyInfo ||
      (isPending && !confirmOid) ||
      result.failure_code === 'MISSING_ORDER_ID' ||
      result.failure_code === 'ORDER_NOT_FOUND_OR_UNAUTHORIZED') &&
    Array.isArray(result.candidate_orders) &&
    result.candidate_orders.length > 0;
  const candidatesHtml = showCandidates ?
    [
      '<div class="pt-1 grid grid-cols-1 gap-2">',
      result.candidate_orders
          .map((cand) => {
            const oid = cand.order_id;
            const prod = escapeHtml(cand.product_name);
            const candPhotoUrl = getProductPhotoUrl(cand.product_name);
            const price = Number(cand.sale_price).toFixed(2);
            const status = escapeHtml(cand.status);
            const promptVal = strings.requestRefundPromptTemplate(oid);
            return [
              '<button type="button"',
              ` data-prompt="${escapeHtml(promptVal)}"`,
              ' class="candidate-order-chip flex items-center gap-3 w-full',
              ' text-xs p-2.5 rounded-lg bg-blue-50/80',
              ' hover:bg-blue-100 text-slate-900 border border-blue-200',
              ' dark:bg-blue-950 dark:hover:bg-blue-800 dark:text-blue-200',
              ' dark:border-blue-700 text-left shadow-xs transition">',
              `<img src="${candPhotoUrl}" alt="${prod}" loading="lazy"`,
              ' class="w-12 h-12 rounded-lg object-cover border',
              ' border-blue-200 bg-white shrink-0">',
              '<div class="min-w-0 flex-1">',
              '<div class="flex items-center justify-between gap-2">',
              '<span class="font-mono font-bold text-blue-800">',
              `ORD-${oid}</span>`,
              '<span class="text-[11px] px-1.5 py-0.5 rounded bg-white',
              ` border border-blue-200 text-slate-700">${status}</span>`,
              '</div>',
              '<div class="font-semibold text-slate-900 truncate">',
              `${prod}</div>`,
              '<div class="text-[11px] font-bold text-emerald-700">',
              `${escapeHtml(strings.clickToRefundPrefix)} &mdash; `,
              `$${price}</div>`,
              '</div>',
              '</button>',
            ].join('');
          })
          .join(''),
      '</div>',
    ].join('') :
    '';

  appendChatMessage(
      'agent',
      [
        '<div class="flex items-center justify-between gap-2">',
        '<span class="font-semibold text-slate-900 dark:text-white">',
        'ADK 2.0 RefundSystemOfActionWorkflow</span>',
        '<span class="px-2 py-0.5 rounded border font-mono text-[11px]',
        ` ${badgeClass}">${escapeHtml(result.decision_status)}</span>`,
        '</div>',
        '<div class="agent-reply-callout p-3.5 rounded-lg shadow-sm',
        ` ${replyCalloutClass}">`,
        '<div class="text-[11px] font-bold uppercase tracking-wider mb-1',
        ` ${replyHeaderColor}">${escapeHtml(replyHeaderText)}</div>`,
        '<p class="text-sm font-medium leading-relaxed">',
        `${escapeHtml(result.reply)}</p>`,
        '</div>',
        orderCardHtml,
        candidatesHtml,
        '<div class="pt-1 border-t border-slate-200 dark:border-slate-800">',
        '<div class="text-[10px] font-semibold uppercase tracking-wider',
        ' text-slate-400 dark:text-slate-500 mb-1">',
        `${escapeHtml(strings.telemetryHeading)}</div>`,
        '<div class="p-2 rounded bg-slate-100/80 border border-slate-200',
        ' dark:bg-slate-950/80 dark:border-slate-800 font-mono text-[11px]',
        ' text-slate-600 dark:text-slate-400 space-y-0.5">',
        '<div>trace_id: <span class="text-blue-700 dark:text-blue-300">',
        `${escapeHtml(result.trace_id)}</span></div>`,
        `<div>tier: ${escapeHtml(pe.customer_tier)}`,
        ` | condition: ${escapeHtml(pe.condition_id)}</div>`,
        `<div>catalog_term: ${escapeHtml(pe.catalog_term_id)}`,
        ` | 100d_returns: ${pe.prior_refund_count_100d}/`,
        `${pe.max_refunds_100d}</div>`,
        '</div>',
        '</div>',
        '<div class="pt-1">',
        `<a href="${traceHref}" class="inline-flex items-center gap-1.5`,
        ' px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white',
        ' font-medium text-xs">',
        `${escapeHtml(strings.inspectConsoleLink)}</a>`,
        '</div>',
      ].join(''),
      requestUserId,
  );

  await refreshCustomersAndOrders();
  const chatInput = document.getElementById('chat-input');
  if (chatInput && !chatInput.disabled) {
    chatInput.focus({preventScroll: true});
  }
}

async function refreshCustomersAndOrders() {
  const response = await fetch('/api/customers');
  const data = await response.json();
  customersCache = data.customers || [];
  renderPersonaCards();
  renderPromptChips();
  updateChatPersonaHeader(activeUserId);
  await loadCustomerOrders(activeUserId);
}

function getResetStages(lang = currentLang) {
  return RESET_STAGES_BY_LANG[lang] || RESET_STAGES_BY_LANG.en;
}

function delayMs(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function renderResetSteps(activeIdx, lang = currentLang) {
  const stepsEl = document.getElementById('reset-progress-steps');
  if (!stepsEl) {
    return;
  }
  const stages = getResetStages(lang);
  stepsEl.innerHTML = stages.map((stage, idx) => {
    const isDone = idx < activeIdx;
    const isCurrent = idx === activeIdx;
    const icon = isDone ? '&#10003;' : isCurrent ? '&#9679;' : '&#9675;';
    const rowTone = isDone ?
      'text-emerald-700 dark:text-emerald-300' :
      isCurrent ?
      'text-amber-700 dark:text-amber-300 font-semibold' :
      'text-slate-400 dark:text-slate-500';
    return [
      `<div class="flex items-start gap-2 ${rowTone}">`,
      `<span class="font-mono mt-0.5">${icon}</span>`,
      '<div>',
      `<div>${escapeHtml(stage.title)}</div>`,
      `<div class="text-[11px] opacity-85">${escapeHtml(stage.detail)}</div>`,
      '</div>',
      '</div>',
    ].join('');
  }).join('');
}

function openResetConfirmModal(targetLang = null) {
  pendingLanguageTarget = targetLang;
  const strings = t();
  const modal = document.getElementById('reset-progress-modal');
  const confirmPanel = document.getElementById('reset-confirm-panel');
  const runningPanel = document.getElementById('reset-running-panel');
  const badgeEl = document.getElementById('reset-confirm-badge');
  const headingEl = document.getElementById('reset-confirm-heading');
  const descEl = document.getElementById('reset-confirm-desc');
  const cancelBtn = document.getElementById('reset-cancel-btn');
  const confirmBtn = document.getElementById('reset-confirm-btn');

  if (targetLang) {
    if (badgeEl) badgeEl.textContent = strings.langSwitchBadge;
    if (headingEl) headingEl.textContent = strings.langSwitchHeading;
    if (descEl) descEl.innerHTML = strings.langSwitchDescHtml;
    if (confirmBtn) confirmBtn.textContent = strings.langSwitchConfirmBtn;
  } else {
    if (badgeEl) badgeEl.textContent = strings.resetConfirmBadge;
    if (headingEl) headingEl.textContent = strings.resetConfirmHeading;
    if (descEl) descEl.innerHTML = strings.resetConfirmDescHtml;
    if (confirmBtn) confirmBtn.textContent = strings.resetConfirmBtn;
  }
  if (cancelBtn) {
    cancelBtn.textContent = strings.resetCancelBtn;
  }

  if (confirmPanel) {
    confirmPanel.classList.remove('hidden');
  }
  if (runningPanel) {
    runningPanel.classList.add('hidden');
  }
  if (modal) {
    modal.classList.remove('hidden');
  }
}

function closeResetConfirmModal() {
  pendingLanguageTarget = null;
  const modal = document.getElementById('reset-progress-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

async function runResetDemoSequence() {
  const switchedToLang = pendingLanguageTarget;
  pendingLanguageTarget = null;
  if (switchedToLang) {
    currentLang = switchedToLang;
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, currentLang);
    } catch {
      // Ignore storage errors in private browsing mode
    }
    applyShopLanguage();
  }

  const strings = t();
  const stages = getResetStages(currentLang);
  const modal = document.getElementById('reset-progress-modal');
  const confirmPanel = document.getElementById('reset-confirm-panel');
  const runningPanel = document.getElementById('reset-running-panel');
  const bar = document.getElementById('reset-progress-bar');
  const pctEl = document.getElementById('reset-progress-pct');
  const statusEl = document.getElementById('reset-progress-status');
  const resetBtn = document.getElementById('reset-demo-btn');
  const langBtn = document.getElementById('lang-toggle-btn');

  setTextById('reset-running-badge', strings.resetRunningBadge);
  setTextById('reset-progress-title', strings.resetRunningTitle);
  setTextById('reset-progress-status', strings.resetRunningPrep);

  if (resetBtn) {
    resetBtn.disabled = true;
  }
  if (langBtn) {
    langBtn.disabled = true;
  }
  if (confirmPanel) {
    confirmPanel.classList.add('hidden');
  }
  if (runningPanel) {
    runningPanel.classList.remove('hidden');
  }
  if (modal) {
    modal.classList.remove('hidden');
  }
  if (bar) {
    bar.style.width = '5%';
  }
  if (pctEl) {
    pctEl.textContent = '5%';
  }

  pendingOrderByUser = {};
  chatHistoryByUser = {};
  clearPersistedChatState();
  const resetFetchPromise = fetch('/api/demo/reset', {method: 'POST'});

  for (let idx = 0; idx < stages.length; idx += 1) {
    const stage = stages[idx];
    renderResetSteps(idx, currentLang);
    if (bar) {
      bar.style.width = `${stage.pct}%`;
    }
    if (pctEl) {
      pctEl.textContent = `${stage.pct}%`;
    }
    if (statusEl) {
      statusEl.textContent = stage.detail;
    }
    if (idx === 2) {
      await resetFetchPromise;
    }
    await delayMs(1050);
  }

  renderResetSteps(stages.length, currentLang);
  await refreshCustomersAndOrders();
  await loadProducts();

  const chatContainer = document.getElementById('chat-messages');
  if (chatContainer) {
    if (currentLang === 'ko') {
      const prefixTitle = switchedToLang ?
        '한국어 전환 및 데모 데이터' +
          ' 초기화 완료:' :
        '데모 데이터 초기화 완료:';
      chatContainer.innerHTML = [
        '<div class="text-xs text-emerald-900 bg-emerald-50 border',
        ' border-emerald-300 dark:text-emerald-200 dark:bg-emerald-950/60',
        ' dark:border-emerald-700 rounded-lg p-3">',
        `<strong>${prefixTitle}</strong> Cloud Spanner 주문`,
        ' (<code class="font-mono font-semibold">ORD-90124</code>,',
        ' <code class="font-mono font-semibold">ORD-90588</code>,',
        ' <code class="font-mono font-semibold">ORD-90910</code>)이',
        ' <code class="font-mono font-semibold">Complete</code> 상태' +
          '로 복원되었으며, UTC 배송 및' +
          ' 100일 반품 타임스탬프 갱신 ' +
          '및 BigQuery <code class="font-mono font-semibold">',
        'soa_action_lineage</code> 환불 트레이스 ' +
          '초기화가 완료되었습니다.',
        '</div>',
      ].join('');
    } else {
      const prefixTitle = switchedToLang ?
        'Switched to English & Demo Data Reset Complete:' :
        'Demo Data Reset Complete:';
      chatContainer.innerHTML = [
        '<div class="text-xs text-emerald-900 bg-emerald-50 border',
        ' border-emerald-300 dark:text-emerald-200 dark:bg-emerald-950/60',
        ' dark:border-emerald-700 rounded-lg p-3">',
        `<strong>${prefixTitle}</strong> Cloud Spanner orders`,
        ' (<code class="font-mono font-semibold">ORD-90124</code>,',
        ' <code class="font-mono font-semibold">ORD-90588</code>,',
        ' <code class="font-mono font-semibold">ORD-90910</code>) restored to',
        ' <code class="font-mono font-semibold">Complete</code> with fresh UTC',
        ' delivery &amp; 100-day return timestamps, and BigQuery',
        ' <code class="font-mono font-semibold">soa_action_lineage</code>',
        ' refund traces cleared.',
        '</div>',
      ].join('');
    }
  }

  if (modal) {
    modal.classList.add('hidden');
  }
  if (resetBtn) {
    resetBtn.disabled = false;
  }
  if (langBtn) {
    langBtn.disabled = false;
  }
}

async function initShopApp() {
  document.documentElement.classList.remove('dark');
  loadPersistedChatState();
  applyShopLanguage();
  await refreshCustomersAndOrders();
  renderChatMessages(activeUserId);
  await loadProducts();

  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  if (chatForm && chatInput) {
    chatForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = chatInput.value;
      chatInput.value = '';
      await submitRefundPrompt(text);
    });
  }

  const clearChatBtn = document.getElementById('clear-chat-btn');
  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      clearActivePersonaChat();
    });
  }

  const langBtn = document.getElementById('lang-toggle-btn');
  if (langBtn) {
    langBtn.addEventListener('click', () => {
      const targetLang = currentLang === 'en' ? 'ko' : 'en';
      openResetConfirmModal(targetLang);
    });
  }

  const resetBtn = document.getElementById('reset-demo-btn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      openResetConfirmModal(null);
    });
  }

  const cancelBtn = document.getElementById('reset-cancel-btn');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      closeResetConfirmModal();
    });
  }

  const confirmBtn = document.getElementById('reset-confirm-btn');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', async () => {
      await runResetDemoSequence();
    });
  }
}

document.addEventListener('DOMContentLoaded', initShopApp);
