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

const CONSOLE_I18N = {
  en: {
    pageTitle:
      'Data Engineer Investigation Console | Dual-Graph System of Action',
    headerTitle: 'Data Engineer Investigation Console',
    headerSubtitle:
      'Dual-Graph Visualizer (Cytoscape.js), ISO GQL Workbench & Spanner ' +
      'Data Boost',
    navShop: 'UI 1: Shopping Mall (/shop)',
    navConsole: 'UI 2: Data Engineer Console (/console)',
    langBtnText: '\uD83C\uDF10 한국어 (KO)',
    langBtnTitle:
      'Switch language to Korean and reset demo dataset ' +
      '(한국어로 전환 및 데모 ' +
      '데이터 초기화)',
    resetBtnText: 'Reset Demo Data',
    emptyTracesTitle: 'No Refund Workflow Traces Recorded Yet',
    emptyTracesDescHtml:
      'Submit a refund request in UI 1 (/shop) as Customer A (1001), ' +
      'Customer B (2048), or Customer C (3072) to populate ' +
      '<code class="text-blue-700 dark:text-blue-300 font-semibold">' +
      'soa_action_lineage.ActionLineageGraph</code>. You can already explore ' +
      'the Cloud Spanner Context Graph and Knowledge Catalog Inspector below.',
    emptyTracesCta: 'Open UI 1 (/shop) \u2192',
    feedSectionTitle: 'Live Refund Request Feed',
    noTracesListText:
      'No traces yet. Submit a refund in UI 1 (/shop) to stream lineage.',
    customerPrefix: 'Customer:',
    returns100dPrefix: '100d Returns:',
    graphSectionTitle: 'Interactive Dual-Graph Visualizer (Cytoscape.js)',
    graphSectionSubtitle:
      'Click any node or edge to inspect its Cloud Spanner or BigQuery ' +
      'properties',
    legendR2g: 'Spanner R2G',
    legendU2g: 'Spanner U2G Policy',
    legendBq: 'BigQuery Lineage',
    nodeInspectorTitle: 'Node Property Inspector',
    nodeInspectorEmpty: 'Click a graph node or edge to view its attributes.',
    workbenchTitle: 'Built-In 3-Tab ISO GQL & Federated Query Workbench',
    workbenchSubtitle:
      'Read-only guarded execution against Cloud Spanner and BigQuery',
    tabSpanner: '1. Cloud Spanner Context Graph (GQL)',
    tabBigquery: '2. BigQuery Action Lineage Graph',
    tabFederated: '3. Federated Spanner Data Boost',
    runQueryBtn: 'Run Query',
    runningQueryStatus: 'Running query...',
    errorStatus: 'Error',
    rowsPrefix: 'Rows:',
    queryPlaceholder: 'Run a query above to inspect tabular results.',
    queryZeroRows: 'Query returned 0 rows.',
    presetSpanner1: 'Activity 1: Customer A (1001 / ORD-90124 Standard)',
    presetSpanner2: 'Activity 2: Customer B (2048 / ORD-90588 Denied)',
    presetSpanner3: 'Activity 3: Customer C (3072 / ORD-90910 VIP)',
    presetBq1: 'Activity 1 & 3: ActionLineageGraph GQL (Approval)',
    presetBq2: 'Activity 2: ActionLineageGraph GQL (Denial)',
    presetBq3: 'Standard SQL JOIN Equivalent (On-Demand Fallback)',
    presetFed1: 'Federated Spanner Data Boost Audit (EXTERNAL_QUERY)',
    catalogCardTitle: 'Knowledge Catalog Semantic Contract',
    catalogCardDescHtml:
      'Governed glossary terms (<code class="font-mono text-indigo-700 ' +
      'dark:text-indigo-300">soa-business-glossary</code>) &amp; Metadata ' +
      'Type (<code class="font-mono text-indigo-700 dark:text-indigo-300">' +
      'refund-metric-contract</code>) resolved in Step 2, bound into Step 3 ' +
      'Cloud Spanner GQL, and attributed in Step 4 BigQuery Lineage',
    previewCatalogLabel: 'Preview Glossary & Contract',
    policyCardTitle: 'Policy Document (U2G) & Extracted Triples',
    policyCardDescHtml:
      'Unstructured-to-Graph (U2G) policy triples extracted from ' +
      '<code class="font-mono text-purple-700 dark:text-purple-300">' +
      'data/policies/return_policy_v1.md</code> into Cloud Spanner ' +
      '<code class="font-mono">OperationalContextGraph</code>',
    previewPolicyLabel: 'Preview return_policy_v1.md',
    catalogModalTitleHtml:
      'Knowledge Catalog Semantic Contract (<code class="font-mono text-xs ' +
      'text-indigo-700 dark:text-indigo-300">soa-business-glossary</code> ' +
      '&amp; <code class="font-mono text-xs text-indigo-700 ' +
      'dark:text-indigo-300">refund-metric-contract</code>)',
    catalogModalSubtitle:
      'How governed business terms and metadata contracts ground the ADK 2.0 ' +
      'workflow across Cloud Spanner and BigQuery',
    catalogModalFlowHtml:
      '<span class="font-semibold text-indigo-900 dark:text-indigo-200">' +
      'Semantic Governance Flow:</span> ' +
      '<code class="font-mono text-[11px] text-indigo-800 ' +
      'dark:text-indigo-300">Knowledge Catalog</code> &rarr; resolved in ' +
      '<code class="font-mono text-[11px] text-indigo-800 ' +
      'dark:text-indigo-300">Step 2 (resolve_catalog_contract)</code> &rarr; ' +
      'bound as parameters in <code class="font-mono text-[11px] ' +
      'text-teal-700 dark:text-teal-300">Step 3 (OperationalContextGraph ' +
      'GQL)</code> &rarr; attributed in <code class="font-mono text-[11px] ' +
      'text-emerald-700 dark:text-emerald-300">Step 4 (BigQuery ' +
      'ActionLineageGraph)</code>.',
    catalogTabOverview: 'Overview & Governed Terms',
    catalogTabRaw: 'Raw Glossary JSON',
    policyModalTitleHtml:
      'Source Policy Document Preview (<code class="font-mono text-xs ' +
      'text-purple-700 dark:text-purple-300">' +
      'data/policies/return_policy_v1.md</code>)',
    policyModalSubtitle:
      'How unstructured corporate policy prose is converted into structured ' +
      'Cloud Spanner Graph policy nodes',
    policyModalFlowHtml:
      '<span class="font-semibold text-purple-900 dark:text-purple-200">' +
      'Unstructured-to-Graph (U2G) Conversion Pipeline:</span> ' +
      '<code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">return_policy_v1.md</code> &rarr; extracted ' +
      'into <code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">u2g_policy_triples.json</code> &rarr; seeded as ' +
      '<code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">policies</code>, <code class="font-mono ' +
      'text-[11px] text-purple-800 dark:text-purple-300">policy_conditions' +
      '</code>, and <code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">policy_restrictions</code> in Cloud Spanner ' +
      '<code class="font-mono text-[11px] text-teal-700 dark:text-teal-300">' +
      'OperationalContextGraph</code>.',
    policyTabRendered: 'Rendered Policy',
    policyTabRaw: 'Raw Markdown (.md)',
    modalCloseBtn: '\u2715 Close',
    modalDoneBtn: 'Done',
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
      '데이터 엔지니어 분석 콘솔' +
      ' | Dual-Graph System of Action',
    headerTitle:
      '데이터 엔지니어 분석 콘솔',
    headerSubtitle:
      '듀얼 그래프 시각화 (Cytoscape.js), ' +
      'ISO GQL 워크벤치 및 Spanner Data Boost',
    navShop: 'UI 1: 쇼핑몰 (/shop)',
    navConsole:
      'UI 2: 데이터 엔지니어 콘솔 ' +
      '(/console)',
    langBtnText: '\uD83C\uDF10 English (EN)',
    langBtnTitle:
      '영어로 전환 및 데모 데이터' +
      ' 초기화 (Switch language to English and reset demo data)',
    resetBtnText: '데모 데이터 초기화',
    emptyTracesTitle:
      '아직 기록된 환불 워크플로 ' +
      '트레이스가 없습니다',
    emptyTracesDescHtml:
      'UI 1 (/shop)에서 고객 A (1001), 고객 B ' +
      '(2048), 또는 고객 C (3072)로 환불을 ' +
      '요청하면 <code class="text-blue-700 ' +
      'dark:text-blue-300 font-semibold">' +
      'soa_action_lineage.ActionLineageGraph</code>에 리니지' +
      '가 기록됩니다. 아래 Cloud Spanner ' +
      '컨텍스트 그래프 및 Knowledge Catalog ' +
      '인스펙터는 즉시 조회할 수 ' +
      '있습니다.',
    emptyTracesCta: 'UI 1 (/shop) 열기 \u2192',
    feedSectionTitle: '실시간 환불 요청 피드',
    noTracesListText:
      '아직 트레이스가 없습니다. ' +
      'UI 1 (/shop)에서 환불을 요청하세' +
      '요.',
    customerPrefix: '고객:',
    returns100dPrefix: '100일 반품:',
    graphSectionTitle:
      '인터랙티브 듀얼 그래프 ' +
      '시각화 (Cytoscape.js)',
    graphSectionSubtitle:
      '노드 또는 엣지를 클릭하여 ' +
      'Cloud Spanner 및 BigQuery 속성을 확인하' +
      '세요',
    legendR2g: 'Spanner R2G (운영)',
    legendU2g: 'Spanner U2G (정책)',
    legendBq: 'BigQuery (리니지)',
    nodeInspectorTitle: '노드 속성 인스펙터',
    nodeInspectorEmpty:
      '그래프 노드 또는 엣지를 ' +
      '클릭하면 속성 정보가 표시' +
      '됩니다.',
    workbenchTitle:
      '내장 3-탭 ISO GQL 및 연합 쿼리 ' +
      '워크벤치',
    workbenchSubtitle:
      'Cloud Spanner 및 BigQuery 대상 읽기 전용 ' +
      '보호 실행',
    tabSpanner: '1. Cloud Spanner 컨텍스트 그래프' +
      ' (GQL)',
    tabBigquery: '2. BigQuery 액션 리니지 그래프',
    tabFederated: '3. Spanner Data Boost 연합 쿼리',
    runQueryBtn: '쿼리 실행',
    runningQueryStatus: '쿼리 실행 중...',
    errorStatus: '오류',
    rowsPrefix: '행 수:',
    queryPlaceholder:
      '위에서 쿼리를 실행하면 ' +
      '테이블 결과가 표시됩니다.',
    queryZeroRows: '쿼리 결과가 0건입니다.',
    presetSpanner1:
      '활동 1: 고객 A (1001 / ORD-90124 Standard 승인)',
    presetSpanner2:
      '활동 2: 고객 B (2048 / ORD-90588 한도 초' +
      '과 거절)',
    presetSpanner3:
      '활동 3: 고객 C (3072 / ORD-90910 VIP 승인)',
    presetBq1:
      '활동 1 & 3: ActionLineageGraph GQL (승인 리니' +
      '지)',
    presetBq2:
      '활동 2: ActionLineageGraph GQL (거절 리니지)',
    presetBq3:
      '표준 SQL JOIN 동치 쿼리 (온디맨' +
      '드 호환)',
    presetFed1:
      'Spanner Data Boost 연합 감사 쿼리 ' +
      '(EXTERNAL_QUERY)',
    catalogCardTitle: 'Knowledge Catalog 시맨틱 계약',
    catalogCardDescHtml:
      'Step 2에서 확인되어 Step 3 Cloud Spanner GQL ' +
      '및 Step 4 BigQuery 리니지에 바인딩' +
      '되는 거버넌스 용어집 ' +
      '(<code class="font-mono text-indigo-700 dark:text-indigo-300">' +
      'soa-business-glossary</code>) 및 메타데이터 ' +
      '타입 (<code class="font-mono text-indigo-700 ' +
      'dark:text-indigo-300">refund-metric-contract</code>)',
    previewCatalogLabel:
      '용어집 & 시맨틱 계약 미리보' +
      '기',
    policyCardTitle:
      '정책 문서 (U2G) & 추출된 트리플',
    policyCardDescHtml:
      '<code class="font-mono text-purple-700 dark:text-purple-300">' +
      'data/policies/return_policy_v1.md</code>에서 Cloud Spanner ' +
      '<code class="font-mono">OperationalContextGraph</code>로 추출' +
      '된 비정형-그래프 (U2G) 정책 ' +
      '트리플',
    previewPolicyLabel: 'return_policy_v1.md 미리보기',
    catalogModalTitleHtml:
      'Knowledge Catalog 시맨틱 계약 (<code ' +
      'class="font-mono text-xs text-indigo-700 dark:text-indigo-300">' +
      'soa-business-glossary</code> &amp; <code class="font-mono text-xs ' +
      'text-indigo-700 dark:text-indigo-300">refund-metric-contract</code>)',
    catalogModalSubtitle:
      '거버넌스 비즈니스 용어 및 ' +
      '메타데이터 계약이 Cloud Spanner와 ' +
      'BigQuery 전반에서 ADK 2.0 워크플로를' +
      ' 그라운딩하는 방식',
    catalogModalFlowHtml:
      '<span class="font-semibold text-indigo-900 dark:text-indigo-200">' +
      '시맨틱 거버넌스 흐름:</span> ' +
      '<code class="font-mono text-[11px] text-indigo-800 ' +
      'dark:text-indigo-300">Knowledge Catalog</code> &rarr; ' +
      '<code class="font-mono text-[11px] text-indigo-800 ' +
      'dark:text-indigo-300">Step 2 (resolve_catalog_contract)</code>에' +
      '서 확인 &rarr; <code class="font-mono text-[11px] ' +
      'text-teal-700 dark:text-teal-300">Step 3 (OperationalContextGraph ' +
      'GQL)</code> 파라미터 바인딩 &rarr; ' +
      '<code class="font-mono text-[11px] text-emerald-700 ' +
      'dark:text-emerald-300">Step 4 (BigQuery ActionLineageGraph)</code> ' +
      '리니지 기록.',
    catalogTabOverview: '개요 & 거버넌스 용어',
    catalogTabRaw: '원본 JSON',
    policyModalTitleHtml:
      '원본 정책 문서 미리보기 ' +
      '(<code class="font-mono text-xs text-purple-700 dark:text-purple-300">' +
      'data/policies/return_policy_v1.md</code>)',
    policyModalSubtitle:
      '비정형 기업 반품 정책 문서' +
      '가 Cloud Spanner Graph 정책 노드로 변환' +
      '되는 과정',
    policyModalFlowHtml:
      '<span class="font-semibold text-purple-900 dark:text-purple-200">' +
      '비정형-그래프 (U2G) 변환 파이' +
      '프라인:</span> <code class="font-mono text-[11px] ' +
      'text-purple-800 dark:text-purple-300">return_policy_v1.md</code> ' +
      '&rarr; <code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">u2g_policy_triples.json</code> 추출 ' +
      '&rarr; Cloud Spanner <code class="font-mono text-[11px] text-teal-700 ' +
      'dark:text-teal-300">OperationalContextGraph</code>의 ' +
      '<code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">policies</code>, <code class="font-mono ' +
      'text-[11px] text-purple-800 dark:text-purple-300">policy_conditions' +
      '</code>, <code class="font-mono text-[11px] text-purple-800 ' +
      'dark:text-purple-300">policy_restrictions</code>로 적재.',
    policyTabRendered: '렌더링된 정책',
    policyTabRaw: '원본 Markdown (.md)',
    modalCloseBtn: '\u2715 닫기',
    modalDoneBtn: '확인',
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
      title: 'Step 4/4: Reloading Live Trace Feed & Dual-Graph Canvas',
      detail:
        'Refreshing BigQuery ActionLineageGraph trace list and resetting ' +
        'Cytoscape.js graph inspector \u2014 Demo reset complete!',
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
        '4/4단계: 실시간 트레이스 피' +
        '드 및 듀얼 그래프 새로고침',
      detail:
        'BigQuery ActionLineageGraph 트레이스 목록 ' +
        '및 Cytoscape.js 그래프 인스펙터 ' +
        '새로고침 \u2014 데모 초기화 ' +
        '완료!',
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
let activeTab = 'spanner';
let activePresetIdx = 0;
let selectedTraceId = 'trace-a1b2c3d4';
let loadedTraces = [];
let cachedGovernanceData = null;
let spannerConnectionId = 'project.us-central1.spanner-data-boost';
let cyInstance = null;

function t() {
  return CONSOLE_I18N[currentLang] || CONSOLE_I18N.en;
}

function setTextById(id, text) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = text;
  }
}

function setHtmlById(id, html) {
  const el = document.getElementById(id);
  if (el) {
    el.innerHTML = html;
  }
}

function applyConsoleLanguage() {
  const strings = t();
  document.documentElement.lang = currentLang;
  document.title = strings.pageTitle;
  setTextById('console-header-title', strings.headerTitle);
  setTextById('console-header-subtitle', strings.headerSubtitle);
  setTextById('nav-shop-link', strings.navShop);
  setTextById('nav-console-link', strings.navConsole);
  setTextById('reset-demo-btn', strings.resetBtnText);
  setTextById('empty-traces-title', strings.emptyTracesTitle);
  setHtmlById('empty-traces-desc', strings.emptyTracesDescHtml);
  setTextById('empty-traces-cta', strings.emptyTracesCta);
  setTextById('feed-section-title', strings.feedSectionTitle);
  setTextById('graph-section-title', strings.graphSectionTitle);
  setTextById('graph-section-subtitle', strings.graphSectionSubtitle);
  setTextById('legend-r2g', strings.legendR2g);
  setTextById('legend-u2g', strings.legendU2g);
  setTextById('legend-bq', strings.legendBq);
  setTextById('node-inspector-title', strings.nodeInspectorTitle);
  setTextById('workbench-title', strings.workbenchTitle);
  setTextById('workbench-subtitle', strings.workbenchSubtitle);
  setTextById('tab-btn-spanner', strings.tabSpanner);
  setTextById('tab-btn-bigquery', strings.tabBigquery);
  setTextById('tab-btn-federated', strings.tabFederated);
  setTextById('run-query-btn', strings.runQueryBtn);
  setTextById('query-results-placeholder', strings.queryPlaceholder);
  setTextById('catalog-card-title', strings.catalogCardTitle);
  setHtmlById('catalog-card-desc', strings.catalogCardDescHtml);
  setTextById('preview-catalog-contract-label', strings.previewCatalogLabel);
  setTextById('policy-card-title', strings.policyCardTitle);
  setHtmlById('policy-card-desc', strings.policyCardDescHtml);
  setTextById('preview-policy-doc-label', strings.previewPolicyLabel);
  setHtmlById('catalog-modal-title', strings.catalogModalTitleHtml);
  setTextById('catalog-modal-subtitle', strings.catalogModalSubtitle);
  setHtmlById('catalog-modal-flow-banner', strings.catalogModalFlowHtml);
  setTextById('catalog-tab-overview', strings.catalogTabOverview);
  setTextById('catalog-tab-raw', strings.catalogTabRaw);
  setHtmlById('policy-modal-title', strings.policyModalTitleHtml);
  setTextById('policy-modal-subtitle', strings.policyModalSubtitle);
  setHtmlById('policy-modal-flow-banner', strings.policyModalFlowHtml);
  setTextById('policy-tab-rendered', strings.policyTabRendered);
  setTextById('policy-tab-raw', strings.policyTabRaw);
  setTextById('close-catalog-contract-modal-btn', strings.modalCloseBtn);
  setTextById('close-policy-doc-modal-btn', strings.modalCloseBtn);
  setTextById('close-catalog-contract-footer-btn', strings.modalDoneBtn);
  setTextById('close-policy-doc-footer-btn', strings.modalDoneBtn);

  const langBtn = document.getElementById('lang-toggle-btn');
  if (langBtn) {
    langBtn.textContent = strings.langBtnText;
    langBtn.title = strings.langBtnTitle;
  }

  if (cachedGovernanceData) {
    const catalogOverviewEl = document.getElementById(
        'catalog-contract-overview-view',
    );
    if (catalogOverviewEl) {
      catalogOverviewEl.innerHTML = renderCatalogContractOverviewHtml(
          cachedGovernanceData.catalog_contract,
          cachedGovernanceData.glossary_terms,
      );
    }
  }
}

function isSelectedTraceDenial(traceId) {
  const found = loadedTraces.find((tItem) => tItem.trace_id === traceId);
  if (!found) return false;
  return (
    found.evaluation_result === 'FAIL' ||
    found.decision_status === 'DENIED'
  );
}

function escapeHtml(value) {
  return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll('\'', '&#39;');
}

const SQL_GQL_KEYWORDS = new Set([
  'GRAPH',
  'MATCH',
  'OPTIONAL',
  'WHERE',
  'RETURN',
  'GROUP',
  'BY',
  'NEXT',
  'SELECT',
  'FROM',
  'JOIN',
  'ON',
  'AND',
  'OR',
  'IN',
  'AS',
  'DISTINCT',
  'ORDER',
  'DESC',
  'ASC',
  'GRAPH_TABLE',
  'EXTERNAL_QUERY',
  'INTERVAL',
  'DAY',
  'STRING',
  'INT64',
  'FLOAT64',
  'BOOL',
  'TRUE',
  'FALSE',
  'NULL',
]);

const SQL_GQL_FUNCTIONS = new Set([
  'COUNT',
  'SUM',
  'ROUND',
  'COALESCE',
  'TIMESTAMP_DIFF',
  'TIMESTAMP_SUB',
  'CURRENT_TIMESTAMP',
  'STRING_AGG',
  'CAST',
]);

function highlightJson(value) {
  const jsonText =
    typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const tokenRegex = new RegExp(
      '("(?:\\\\u[a-zA-Z0-9]{4}|\\\\[^u]|[^\\\\"])*"(?:\\s*:)?|' +
      '\\b(?:true|false|null)\\b|-?\\d+(?:\\.\\d*)?(?:[eE][+\\-]?\\d+)?|' +
      '[{}\\[\\],])',
      'g',
  );
  let out = '';
  let lastIdx = 0;
  let match = tokenRegex.exec(jsonText);
  while (match !== null) {
    out += escapeHtml(jsonText.slice(lastIdx, match.index));
    const tok = match[0];
    if (tok.startsWith('"')) {
      if (tok.endsWith(':')) {
        const colonIdx = tok.lastIndexOf(':');
        const keyPart = escapeHtml(tok.slice(0, colonIdx));
        const colonPart = escapeHtml(tok.slice(colonIdx));
        out +=
          `<span class="text-indigo-700 font-semibold">${keyPart}</span>` +
          `<span class="text-slate-500">${colonPart}</span>`;
      } else {
        out +=
          `<span class="text-emerald-700">${escapeHtml(tok)}</span>`;
      }
    } else if (tok === 'true' || tok === 'false' || tok === 'null') {
      out +=
        '<span class="text-purple-700 font-semibold">' +
        `${escapeHtml(tok)}</span>`;
    } else if (
      tok === '{' ||
      tok === '}' ||
      tok === '[' ||
      tok === ']' ||
      tok === ','
    ) {
      out += `<span class="text-slate-500">${escapeHtml(tok)}</span>`;
    } else {
      out +=
        '<span class="text-amber-700 font-semibold">' +
        `${escapeHtml(tok)}</span>`;
    }
    lastIdx = tokenRegex.lastIndex;
    match = tokenRegex.exec(jsonText);
  }
  out += escapeHtml(jsonText.slice(lastIdx));
  return out;
}

function highlightSqlGql(sqlText) {
  const text = String(sqlText ?? '');
  const tokenRegex = new RegExp(
      '(--[^\\n]*|\'\'\'|\'(?:\\\\.|[^\'\\\\])*\'|`[^`]*`|' +
      ':[A-Za-z_][A-Za-z0-9_]*|\\b[A-Za-z_][A-Za-z0-9_]*\\b|' +
      '\\b\\d+(?:\\.\\d+)?\\b)',
      'g',
  );
  let out = '';
  let lastIdx = 0;
  let match = tokenRegex.exec(text);
  while (match !== null) {
    out += escapeHtml(text.slice(lastIdx, match.index));
    const tok = match[0];
    if (tok.startsWith('--')) {
      out += `<span class="text-slate-500 italic">${escapeHtml(tok)}</span>`;
    } else if (tok === '\'\'\'') {
      out += `<span class="text-amber-700 font-bold">${escapeHtml(tok)}</span>`;
    } else if (tok.startsWith('\'')) {
      out += `<span class="text-emerald-700">${escapeHtml(tok)}</span>`;
    } else if (tok.startsWith('`')) {
      out +=
        `<span class="text-teal-700 font-semibold">${escapeHtml(tok)}</span>`;
    } else if (tok.startsWith(':')) {
      out +=
        `<span class="text-purple-700 font-semibold">${escapeHtml(tok)}</span>`;
    } else if (/^\d/.test(tok)) {
      out +=
        `<span class="text-amber-700 font-semibold">${escapeHtml(tok)}</span>`;
    } else {
      const upper = tok.toUpperCase();
      if (SQL_GQL_KEYWORDS.has(upper)) {
        out +=
          `<span class="text-blue-700 font-bold">${escapeHtml(tok)}</span>`;
      } else if (SQL_GQL_FUNCTIONS.has(upper)) {
        out +=
          '<span class="text-indigo-600 font-semibold">' +
          `${escapeHtml(tok)}</span>`;
      } else if (
        tok === 'OperationalContextGraph' ||
        tok === 'ActionLineageGraph'
      ) {
        out +=
          `<span class="text-purple-700 font-bold">${escapeHtml(tok)}</span>`;
      } else {
        out += escapeHtml(tok);
      }
    }
    lastIdx = tokenRegex.lastIndex;
    match = tokenRegex.exec(text);
  }
  out += escapeHtml(text.slice(lastIdx));
  return out;
}

function syncQueryHighlight() {
  const editor = document.getElementById('query-editor');
  const highlightEl = document.getElementById('query-highlight-view');
  if (!editor || !highlightEl) return;
  highlightEl.innerHTML = `${highlightSqlGql(editor.value)}\n`;
  highlightEl.scrollTop = editor.scrollTop;
  highlightEl.scrollLeft = editor.scrollLeft;
}

function getCytoscapeStylesheet() {
  const isDark = document.documentElement.classList.contains('dark');
  const nodeLabelColor = isDark ? '#f8fafc' : '#0f172a';
  const edgeLabelColor = isDark ? '#94a3b8' : '#475569';
  const edgeLineColor = isDark ? '#475569' : '#94a3b8';
  return [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'color': nodeLabelColor,
        'font-size': '10px',
        'text-wrap': 'wrap',
        'text-valign': 'bottom',
        'text-margin-y': 5,
        'background-color': '#3b82f6',
        'width': 32,
        'height': 32,
      },
    },
    {
      selector: 'node[layer = "u2g"]',
      style: {'background-color': '#a855f7'},
    },
    {
      selector: 'node[layer = "bq"]',
      style: {'background-color': '#10b981'},
    },
    {
      selector: 'edge',
      style: {
        'label': 'data(label)',
        'font-size': '9px',
        'color': edgeLabelColor,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'line-color': edgeLineColor,
        'target-arrow-color': edgeLineColor,
        'width': 1.5,
      },
    },
  ];
}

function buildSpannerGqlPreset(userId, orderId) {
  const headerComments = currentLang === 'ko' ?
    [
      `-- 목적: 고객 user_id=${userId} 및 대상 ` +
        `주문 ORD-${orderId}의 실시간 환불 ` +
        '적격성 평가.',
      '-- 대상 엔진: Cloud Spanner (thelook-soa-db / ' +
        'OperationalContextGraph).',
      '-- 작동 방식: 1단계는 R2G 경로 ' +
        '(users -> orders -> inventory_items -> products -> ' +
        'distribution_centers) 및',
      '--   U2G 경로 (products -> policies -> policy_conditions / ' +
        'policy_restrictions)를 탐색하고, 2단계 ' +
        '(NEXT)는',
      '--   최근 100일 내 반품된 아이템' +
        ' 개수를 OPTIONAL MATCH로 집계합니' +
        '다.',
    ] :
    [
      '-- Purpose: Evaluate live operational refund eligibility for Customer',
      `--   user_id=${userId} and target order ORD-${orderId}.`,
      '-- Target Engine: Cloud Spanner (thelook-soa-db /',
      '--   OperationalContextGraph).',
      '-- How It Works: Stage 1 traverses the Relational-to-Graph (R2G) path:',
      '--   users -> orders -> inventory_items -> products ->',
      '--   distribution_centers, plus the Unstructured-to-Graph (U2G) path:',
      '--   products -> policies -> policy_conditions / policy_restrictions,',
      '--   matching the condition for the customer\'s loyalty tier',
      '--   (STANDARD or VIP). Stage 2 (NEXT) runs an OPTIONAL MATCH over',
      '--   the customer\'s historical orders to count distinct returned',
      '--   items within the trailing 100-day window.',
      '-- Information Gathered: customer_tier, target_order_status,',
      '--   target_order_age_days, target_order_price, product_names,',
      '--   prior_refund_count_100d, condition_id, max_refunds_100d,',
      '--   return_window_days, and restriction_action.',
    ];
  return [
    ...headerComments,
    'GRAPH OperationalContextGraph',
    '-- Stage 1: Traverse R2G order/product context and U2G tier policy rules',
    `MATCH (u:users {id: ${userId}})`,
    `        -[:places]->(target_o:orders {order_id: ${orderId}})`,
    '        -[target_oi:contains_item]->(ii:inventory_items)',
    '        -[:is_product]->(p:products)',
    '        -[:supplied_by]->(dc:distribution_centers),',
    '      (p)-[:governed_by]->(pol:policies {status: \'ACTIVE\'})',
    '        -[:requires_condition]->(cond:policy_conditions),',
    '      (pol)-[:enforces_restriction]->(res:policy_restrictions)',
    'WHERE u.customer_tier IN (\'STANDARD\', \'VIP\')',
    '  AND cond.applicable_tier = u.customer_tier',
    'RETURN',
    '  u.id AS user_id,',
    '  u.email AS email,',
    '  u.customer_tier AS customer_tier,',
    '  target_o.order_id AS target_order_id,',
    '  target_o.status AS target_order_status,',
    '  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), target_o.delivered_at, DAY)',
    '    AS target_order_age_days,',
    '  ROUND(SUM(target_oi.sale_price), 2) AS target_order_price,',
    '  STRING_AGG(DISTINCT p.name, \', \') AS product_names,',
    '  STRING_AGG(DISTINCT dc.name, \', \') AS distribution_center_names,',
    '  pol.policy_id AS policy_id,',
    '  pol.name AS policy_name,',
    '  cond.condition_id AS condition_id,',
    '  cond.max_refunds_100d AS max_refunds_100d,',
    '  cond.return_window_days AS return_window_days,',
    '  res.action_code AS restriction_action',
    'GROUP BY',
    '  user_id, email, customer_tier, target_order_id, target_order_status,',
    '  target_order_age_days, policy_id, policy_name, condition_id,',
    '  max_refunds_100d, return_window_days, restriction_action',
    'NEXT',
    '-- Stage 2: Count prior returned items in the rolling 100-day window',
    'OPTIONAL MATCH (u2:users)-[:places]->(hist_o:orders)',
    '               -[hist_oi:contains_item]->(:inventory_items)',
    'WHERE u2.id = user_id',
    '  AND hist_o.order_id != target_order_id',
    '  AND hist_oi.status = \'Returned\'',
    '  AND COALESCE(hist_oi.returned_at, hist_o.returned_at,',
    '      hist_o.created_at) >= TIMESTAMP_SUB(',
    '      CURRENT_TIMESTAMP(), INTERVAL 100 DAY)',
    'RETURN',
    '  user_id, email, customer_tier, target_order_id, target_order_status,',
    '  product_names, distribution_center_names, target_order_price,',
    '  target_order_age_days,',
    '  COUNT(DISTINCT hist_oi.id) AS prior_refund_count_100d,',
    '  policy_id, policy_name, condition_id, max_refunds_100d,',
    '  return_window_days, restriction_action',
    'GROUP BY',
    '  user_id, email, customer_tier, target_order_id, target_order_status,',
    '  product_names, distribution_center_names, target_order_price,',
    '  target_order_age_days, policy_id, policy_name, condition_id,',
    '  max_refunds_100d, return_window_days, restriction_action',
  ].join('\n');
}

function buildBqGqlApprovalPreset(traceId) {
  return [
    '-- Purpose: Audit the immutable 4-hop execution lineage for workflow',
    `--   trace '${traceId}' in the BigQuery Action Lineage Graph.`,
    '-- Target Engine: BigQuery Graph (soa_action_lineage.ActionLineageGraph)',
    '-- How It Works: Uses ISO GQL GRAPH_TABLE to traverse AgentSession ->',
    '--   WorkflowNode (evaluate_spanner_policy) -> PolicyEvaluation ->',
    '--   AgentAction along directed lineage edges.',
    '-- Information Gathered: trace_id, customer_id, target_order_id,',
    '--   catalog_term_id (Knowledge Catalog term), policy_name,',
    '--   prior_refund_count_100d, max_refunds_100d, evaluation_result,',
    '--   action_type, decision_status, and committed_at timestamp.',
    'SELECT',
    '  trace_id, customer_id, target_order_id, node_name, catalog_term_id,',
    '  policy_name, prior_refund_count_100d, max_refunds_100d,',
    '  evaluation_result, action_type, decision_status, committed_at',
    'FROM GRAPH_TABLE(soa_action_lineage.ActionLineageGraph',
    '  MATCH (s:AgentSession)',
    '        -[:executed_node]->(n:WorkflowNode',
    '          {node_name: \'evaluate_spanner_policy\'})',
    '        -[:evaluated_policy]->(pe:PolicyEvaluation)',
    '        -[:triggered_action]->(act:AgentAction)',
    '  -- Tip: Comment out the WHERE line below to query ALL traces:',
    `  WHERE s.trace_id = '${traceId}'`,
    '  RETURN',
    '    s.trace_id AS trace_id,',
    '    s.customer_id AS customer_id,',
    '    s.target_order_id AS target_order_id,',
    '    n.node_name AS node_name,',
    '    pe.catalog_term_id AS catalog_term_id,',
    '    pe.policy_name AS policy_name,',
    '    pe.observed_refunds_100d AS prior_refund_count_100d,',
    '    pe.max_refunds_100d AS max_refunds_100d,',
    '    pe.evaluation_result AS evaluation_result,',
    '    act.action_type AS action_type,',
    '    act.decision_status AS decision_status,',
    '    act.created_at AS committed_at',
    ')',
  ].join('\n');
}

function buildBqGqlDenialPreset(traceId) {
  const isDenial = isSelectedTraceDenial(traceId);
  const whereTip = isDenial ?
    '  -- Tip: Comment out the WHERE line below to query ALL denial traces:' :
    '  -- Tip: Uncomment the WHERE line below to filter by selected trace:';
  const whereLine = isDenial ?
    `  WHERE s.trace_id = '${traceId}'` :
    `  -- WHERE s.trace_id = '${traceId}'`;
  return [
    '-- Purpose: Investigate policy denial traces in the BigQuery Action',
    '--   Lineage Graph (supports selected trace or all denial traces).',
    '-- Target Engine: BigQuery Graph (soa_action_lineage.ActionLineageGraph)',
    '-- How It Works: Traverses AgentSession -> WorkflowNode ->',
    '--   PolicyEvaluation {evaluation_result: \'FAIL\'} -> AgentAction using',
    '--   ISO GQL GRAPH_TABLE to isolate blocked refund mutations.',
    '-- Information Gathered: trace_id, customer_id, target_order_id,',
    '--   catalog_term_id, policy_name, prior_refund_count_100d,',
    '--   max_refunds_100d, evaluation_result (\'FAIL\'), action_type',
    '--   (\'BLOCK_SPANNER_MUTATION\'), decision_status (\'DENIED\'), and',
    '--   rejection_reason.',
    'SELECT',
    '  trace_id, customer_id, target_order_id, catalog_term_id, policy_name,',
    '  prior_refund_count_100d, max_refunds_100d, evaluation_result,',
    '  action_type, decision_status, rejection_reason',
    'FROM GRAPH_TABLE(soa_action_lineage.ActionLineageGraph',
    '  MATCH (s:AgentSession)',
    '        -[:executed_node]->(n:WorkflowNode',
    '          {node_name: \'evaluate_spanner_policy\'})',
    '        -[:evaluated_policy]->(pe:PolicyEvaluation',
    '          {evaluation_result: \'FAIL\'})',
    '        -[:triggered_action]->(act:AgentAction)',
    whereTip,
    whereLine,
    '  RETURN',
    '    s.trace_id AS trace_id,',
    '    s.customer_id AS customer_id,',
    '    s.target_order_id AS target_order_id,',
    '    pe.catalog_term_id AS catalog_term_id,',
    '    pe.policy_name AS policy_name,',
    '    pe.observed_refunds_100d AS prior_refund_count_100d,',
    '    pe.max_refunds_100d AS max_refunds_100d,',
    '    pe.evaluation_result AS evaluation_result,',
    '    act.action_type AS action_type,',
    '    act.decision_status AS decision_status,',
    '    act.rejection_reason AS rejection_reason',
    ')',
  ].join('\n');
}

function buildBqSqlJoinPreset(traceId) {
  return [
    '-- Purpose: Relational SQL JOIN equivalent of the ActionLineageGraph',
    `--   traversal for trace '${traceId}' (BigQuery on-demand compatible).`,
    '-- Target Engine: BigQuery (soa_action_lineage relational lineage tables)',
    '-- How It Works: Joins agent_sessions, workflow_nodes,',
    '--   policy_evaluations, and agent_actions along their primary/foreign',
    '--   keys (trace_id -> node_exec_id -> eval_id).',
    '-- Information Gathered: Full end-to-end decision lineage including',
    '--   catalog_term_id, prior_refund_count_100d, max_refunds_100d,',
    '--   evaluation_result, action_type, decision_status, rejection_reason,',
    '--   and committed_at.',
    'SELECT',
    '  s.trace_id, s.customer_id, s.target_order_id, n.node_name,',
    '  pe.catalog_term_id, pe.policy_name,',
    '  pe.observed_refunds_100d AS prior_refund_count_100d,',
    '  pe.max_refunds_100d, pe.evaluation_result, act.action_type,',
    '  act.decision_status, act.rejection_reason,',
    '  act.created_at AS committed_at',
    'FROM `soa_action_lineage.agent_sessions` AS s',
    'JOIN `soa_action_lineage.workflow_nodes` AS n',
    '  ON s.trace_id = n.trace_id',
    ' AND n.node_name = \'evaluate_spanner_policy\'',
    'JOIN `soa_action_lineage.policy_evaluations` AS pe',
    '  ON n.node_exec_id = pe.node_exec_id',
    'JOIN `soa_action_lineage.agent_actions` AS act',
    '  ON pe.eval_id = act.eval_id',
    '-- Tip: Comment out the WHERE line below to query ALL traces:',
    `WHERE s.trace_id = '${traceId}'`,
    'ORDER BY s.started_at DESC',
  ].join('\n');
}

function buildFederatedDataBoostPreset() {
  return [
    '-- Purpose: Cross-engine federated audit reconciling immutable BigQuery',
    '--   action lineage with live Cloud Spanner operational graph state.',
    '-- Target Engine: BigQuery federated with Cloud Spanner Data Boost',
    `--   via EXTERNAL_QUERY connection '${spannerConnectionId}'.`,
    '-- How It Works: Joins BigQuery\'s 4 lineage tables (agent_sessions,',
    '--   workflow_nodes, policy_evaluations, agent_actions) with 3',
    '--   root-partitionable ISO GQL EXTERNAL_QUERY subqueries pushed down to',
    '--   isolated Spanner Data Boost compute (scanning users, orders, and',
    '--   contains_item edges without impacting transactional Spanner CPU).',
    '-- Information Gathered: Historical BigQuery decision metrics',
    '--   (prior_refund_count_100d, max_refunds_100d, evaluation_result,',
    '--   decision_status) side-by-side with live Cloud Spanner state',
    '--   (live_spanner_email, live_spanner_tier, live_spanner_order_status,',
    '--   live_spanner_returned_at, and live_spanner_refund_trace_id).',
    'SELECT',
    '  s.trace_id,',
    '  sp_u.email AS live_spanner_email,',
    '  sp_u.customer_tier AS live_spanner_tier,',
    '  s.target_order_id,',
    '  sp_o.live_spanner_order_status,',
    '  sp_o.live_spanner_returned_at,',
    '  sp_oi.live_spanner_refund_trace_id,',
    '  pe.observed_refunds_100d AS prior_refund_count_100d,',
    '  pe.max_refunds_100d,',
    '  pe.evaluation_result,',
    '  act.action_type,',
    '  act.decision_status',
    'FROM `soa_action_lineage.agent_sessions` AS s',
    'JOIN `soa_action_lineage.workflow_nodes` AS n',
    '  ON s.trace_id = n.trace_id',
    ' AND n.node_name = \'evaluate_spanner_policy\'',
    'JOIN `soa_action_lineage.policy_evaluations` AS pe',
    '  ON n.node_exec_id = pe.node_exec_id',
    'JOIN `soa_action_lineage.agent_actions` AS act',
    '  ON pe.eval_id = act.eval_id',
    '-- EXTERNAL_QUERY 1: Push down ISO GQL scan of live Spanner user tiers',
    'JOIN EXTERNAL_QUERY(',
    `  '${spannerConnectionId}',`,
    '  \'\'\'',
    '  GRAPH OperationalContextGraph',
    '  MATCH (u:users)',
    '  WHERE u.id IN (1001, 2048, 3072)',
    '  RETURN',
    '    u.id AS user_id,',
    '    u.email AS email,',
    '    u.customer_tier AS customer_tier',
    '  \'\'\'',
    ') AS sp_u',
    '  ON s.customer_id = sp_u.user_id',
    '-- EXTERNAL_QUERY 2: Push down ISO GQL scan of live Spanner order status',
    'JOIN EXTERNAL_QUERY(',
    `  '${spannerConnectionId}',`,
    '  \'\'\'',
    '  GRAPH OperationalContextGraph',
    '  MATCH (o:orders)',
    '  WHERE o.user_id IN (1001, 2048, 3072)',
    '  RETURN',
    '    o.user_id AS user_id,',
    '    o.order_id AS order_id,',
    '    o.status AS live_spanner_order_status,',
    '    CAST(o.returned_at AS STRING) AS live_spanner_returned_at',
    '  \'\'\'',
    ') AS sp_o',
    '  ON s.customer_id = sp_o.user_id',
    ' AND s.target_order_id = sp_o.order_id',
    '-- EXTERNAL_QUERY 3: Push down ISO GQL scan of live refund_trace_id keys',
    'JOIN EXTERNAL_QUERY(',
    `  '${spannerConnectionId}',`,
    '  \'\'\'',
    '  GRAPH OperationalContextGraph',
    '  MATCH (:orders)-[oi:contains_item]->(:inventory_items)',
    '  WHERE oi.user_id IN (1001, 2048, 3072)',
    '  RETURN',
    '    oi.order_id AS order_id,',
    '    oi.refund_trace_id AS live_spanner_refund_trace_id',
    '  \'\'\'',
    ') AS sp_oi',
    '  ON s.target_order_id = sp_oi.order_id',
    'ORDER BY s.started_at DESC',
  ].join('\n');
}

function renderPresetButtons() {
  const bar = document.getElementById('preset-buttons-bar');
  const editor = document.getElementById('query-editor');
  if (!bar || !editor) return;
  const strings = t();

  let presets = [];
  if (activeTab === 'spanner') {
    presets = [
      {
        label: strings.presetSpanner1,
        query: buildSpannerGqlPreset(1001, 90124),
      },
      {
        label: strings.presetSpanner2,
        query: buildSpannerGqlPreset(2048, 90588),
      },
      {
        label: strings.presetSpanner3,
        query: buildSpannerGqlPreset(3072, 90910),
      },
    ];
  } else if (activeTab === 'bigquery') {
    presets = [
      {
        label: strings.presetBq1,
        query: buildBqGqlApprovalPreset(selectedTraceId),
      },
      {
        label: strings.presetBq2,
        query: buildBqGqlDenialPreset(selectedTraceId),
      },
      {
        label: strings.presetBq3,
        query: buildBqSqlJoinPreset(selectedTraceId),
      },
    ];
  } else {
    presets = [
      {
        label: strings.presetFed1,
        query: buildFederatedDataBoostPreset(),
      },
    ];
  }

  if (activePresetIdx >= presets.length) {
    activePresetIdx = 0;
  }

  bar.innerHTML = presets
      .map((preset, idx) => {
        const isCurrent = idx === activePresetIdx;
        const btnClass = isCurrent ?
          'preset-btn text-xs px-2.5 py-1 rounded bg-blue-600 text-white ' +
            'border border-blue-600 font-medium' :
          'preset-btn text-xs px-2.5 py-1 rounded bg-blue-50 ' +
            'hover:bg-blue-100 text-blue-700 border border-blue-200 ' +
            'dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-blue-200 ' +
            'dark:border-slate-700';
        return [
          '<button type="button"',
          ` data-preset-idx="${idx}"`,
          ` class="${btnClass}">`,
          escapeHtml(preset.label),
          '</button>',
        ].join('');
      })
      .join('');

  if (presets.length > 0) {
    editor.value = presets[activePresetIdx].query;
    syncQueryHighlight();
  }

  bar.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = Number(btn.getAttribute('data-preset-idx'));
      if (presets[idx]) {
        activePresetIdx = idx;
        renderPresetButtons();
      }
    });
  });
}

async function renderDualGraph(traceId) {
  const container = document.getElementById('cy-canvas');
  const inspector = document.getElementById('node-inspector');
  if (!container) return;
  const response = await fetch(
      `/api/traces/${encodeURIComponent(traceId)}/graph`,
  );
  if (!response.ok) return;
  const graphData = await response.json();
  const elements = [...(graphData.nodes || []), ...(graphData.edges || [])];

  if (cyInstance) {
    cyInstance.destroy();
  }
  const cytoscapeFn = window.cytoscape;
  if (!cytoscapeFn) return;

  cyInstance = cytoscapeFn({
    container,
    elements,
    style: getCytoscapeStylesheet(),
    layout: {name: 'breadthfirst', directed: true, padding: 20},
  });

  cyInstance.on('tap', 'node, edge', (evt) => {
    const data = evt.target.data();
    if (inspector) {
      inspector.innerHTML = highlightJson(data);
    }
  });
}

async function loadTraces() {
  const listEl = document.getElementById('traces-list');
  const banner = document.getElementById('empty-traces-banner');
  const inspector = document.getElementById('node-inspector');
  if (!listEl) return;
  const strings = t();
  const response = await fetch('/api/traces');
  const data = await response.json();
  const traces = data.traces || [];
  loadedTraces = traces;

  if (traces.length === 0) {
    if (banner) banner.classList.remove('hidden');
    if (cyInstance) {
      cyInstance.destroy();
      cyInstance = null;
    }
    if (inspector) {
      inspector.textContent = strings.nodeInspectorEmpty;
    }
    listEl.innerHTML = [
      '<div class="text-xs text-slate-600 dark:text-slate-400 p-3 rounded',
      ' bg-slate-50 border border-slate-200 dark:bg-slate-950',
      ' dark:border-slate-800">',
      escapeHtml(strings.noTracesListText),
      '</div>',
    ].join('');
    return;
  }
  if (banner) banner.classList.add('hidden');

  const urlParams = new URLSearchParams(window.location.search);
  const queryTrace = urlParams.get('trace_id');
  if (queryTrace && traces.some((tItem) => tItem.trace_id === queryTrace)) {
    selectedTraceId = queryTrace;
  } else if (!traces.some((tItem) => tItem.trace_id === selectedTraceId)) {
    selectedTraceId = traces[0].trace_id;
  }

  listEl.innerHTML = traces
      .map((trace) => {
        const isSelected = trace.trace_id === selectedTraceId;
        const borderClass = isSelected ?
        'border-emerald-500 bg-emerald-50/80 dark:bg-emerald-950/30' :
        'border-slate-200 bg-slate-50 hover:border-slate-300 ' +
          'dark:border-slate-800 dark:bg-slate-950/70 ' +
          'dark:hover:border-slate-700';
        const statusBadge =
        trace.decision_status === 'APPROVED' ?
          'bg-emerald-100 text-emerald-800 ' +
            'dark:bg-emerald-900/80 dark:text-emerald-200' :
          trace.decision_status === 'PENDING_CONFIRMATION' ?
            'bg-amber-100 text-amber-800 ' +
              'dark:bg-amber-900/80 dark:text-amber-200' :
            'bg-rose-100 text-rose-800 dark:bg-rose-900/80 dark:text-rose-200';
        const orderLabel = trace.target_order_id ?
        `ORD-${trace.target_order_id}` :
        'N/A';
        return [
          '<button type="button"',
          ` data-trace-id="${escapeHtml(trace.trace_id)}"`,
          ' class="trace-item w-full text-left p-3 rounded-lg border',
          ` transition ${borderClass}">`,
          '<div class="flex items-center justify-between gap-2">',
          '<span class="font-mono text-xs text-blue-700 dark:text-blue-300">',
          `${escapeHtml(trace.trace_id)}</span>`,
          '<span class="text-[10px] px-1.5 py-0.5 rounded font-mono',
          ` ${statusBadge}">${escapeHtml(trace.decision_status)}</span>`,
          '</div>',
          '<div class="text-xs text-slate-700 dark:text-slate-300 mt-1 flex',
          ' justify-between">',
          `<span>${escapeHtml(strings.customerPrefix)} ${trace.customer_id} `,
          `| ${orderLabel}</span>`,
          `<span class="font-mono">${trace.latency_ms} ms</span>`,
          '</div>',
          '<div class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5',
          ' font-mono">',
          `${escapeHtml(strings.returns100dPrefix)} `,
          `${trace.observed_refunds_100d} / `,
          `${trace.max_refunds_100d} (${escapeHtml(trace.evaluation_result)})`,
          '</div>',
          '</button>',
        ].join('');
      })
      .join('');

  listEl.querySelectorAll('.trace-item').forEach((btn) => {
    btn.addEventListener('click', async () => {
      selectedTraceId = btn.getAttribute('data-trace-id') || selectedTraceId;
      await loadTraces();
      renderPresetButtons();
    });
  });

  await renderDualGraph(selectedTraceId);
}

function formatInlineMarkdown(lineText) {
  let html = escapeHtml(lineText);
  html = html.replace(
      /\*\*([^*]+)\*\*/g,
      '<strong class="font-semibold text-slate-900">$1</strong>',
  );
  html = html.replace(
      /`([^`]+)`/g,
      '<code class="px-1 py-0.5 rounded bg-purple-50 text-purple-800 ' +
        'border border-purple-200 font-mono text-[11px]">$1</code>',
  );
  return html;
}

function renderPolicyMarkdownHtml(markdownText) {
  const lines = String(markdownText || '').split('\n');
  const htmlParts = [];
  let inList = false;
  let tableRows = [];

  const flushList = () => {
    if (inList) {
      htmlParts.push('</ul>');
      inList = false;
    }
  };

  const flushTable = () => {
    if (tableRows.length === 0) {
      return;
    }
    const headerCells = tableRows[0];
    const bodyRows = tableRows.slice(2);
    const thHtml = headerCells
        .map(
            (cell) =>
              '<th class="px-3 py-2 text-left text-[11px] font-semibold ' +
              'text-slate-700 bg-slate-100 border-b border-slate-200">' +
              `${formatInlineMarkdown(cell)}</th>`,
        )
        .join('');
    const trHtml = bodyRows
        .map((row) => {
          const tdHtml = row
              .map(
                  (cell) =>
                    '<td class="px-3 py-2 text-xs text-slate-800 border-b ' +
                    `border-slate-200">${formatInlineMarkdown(cell)}</td>`,
              )
              .join('');
          return `<tr>${tdHtml}</tr>`;
        })
        .join('');
    htmlParts.push(
        '<div class="overflow-x-auto my-2 rounded-lg border border-slate-200">',
        '<table class="w-full border-collapse">',
        `<thead><tr>${thHtml}</tr></thead>`,
        `<tbody>${trHtml}</tbody></table></div>`,
    );
    tableRows = [];
  };

  let idx = 0;
  while (idx < lines.length) {
    const rawLine = lines[idx];
    const trimmed = rawLine.trim();

    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      flushList();
      const cells = trimmed
          .slice(1, -1)
          .split('|')
          .map((c) => c.trim());
      tableRows.push(cells);
      idx += 1;
      continue;
    }
    flushTable();

    if (!trimmed) {
      flushList();
      idx += 1;
      continue;
    }

    if (trimmed.startsWith('# ')) {
      flushList();
      htmlParts.push(
          '<h4 class="text-sm font-bold text-slate-900 pb-1 border-b ' +
          `border-slate-200">${formatInlineMarkdown(trimmed.slice(2))}</h4>`,
      );
      idx += 1;
      continue;
    }

    if (trimmed.startsWith('## ')) {
      flushList();
      htmlParts.push(
          '<h5 class="text-xs font-bold text-purple-900 uppercase ' +
          'tracking-wider pt-2">' +
          `${formatInlineMarkdown(trimmed.slice(3))}</h5>`,
      );
      idx += 1;
      continue;
    }

    if (trimmed.startsWith('- ')) {
      if (!inList) {
        htmlParts.push('<ul class="list-disc pl-5 space-y-1.5">');
        inList = true;
      }
      let itemText = trimmed.slice(2);
      while (
        idx + 1 < lines.length &&
        lines[idx + 1].startsWith('  ') &&
        !lines[idx + 1].trim().startsWith('- ')
      ) {
        idx += 1;
        itemText += ` ${lines[idx].trim()}`;
      }
      htmlParts.push(`<li>${formatInlineMarkdown(itemText)}</li>`);
      idx += 1;
      continue;
    }

    flushList();
    let paraText = trimmed;
    while (
      idx + 1 < lines.length &&
      lines[idx + 1].trim() !== '' &&
      !lines[idx + 1].trim().startsWith('#') &&
      !lines[idx + 1].trim().startsWith('- ') &&
      !lines[idx + 1].trim().startsWith('|')
    ) {
      idx += 1;
      paraText += ` ${lines[idx].trim()}`;
    }
    htmlParts.push(`<p>${formatInlineMarkdown(paraText)}</p>`);
    idx += 1;
  }

  flushList();
  flushTable();
  return htmlParts.join('');
}

function setPolicyModalTab(mode) {
  const renderedView = document.getElementById('policy-doc-rendered-view');
  const rawView = document.getElementById('policy-doc-raw-view');
  const renderedBtn = document.getElementById('policy-tab-rendered');
  const rawBtn = document.getElementById('policy-tab-raw');
  const isRaw = mode === 'raw';
  if (renderedView) {
    renderedView.classList.toggle('hidden', isRaw);
  }
  if (rawView) {
    rawView.classList.toggle('hidden', !isRaw);
  }
  if (renderedBtn) {
    renderedBtn.className = !isRaw ?
      'px-2.5 py-1 rounded-md bg-purple-600 text-white text-xs ' +
        'font-medium transition' :
      'px-2.5 py-1 rounded-md text-slate-700 dark:text-slate-300 ' +
        'text-xs font-medium transition';
  }
  if (rawBtn) {
    rawBtn.className = isRaw ?
      'px-2.5 py-1 rounded-md bg-purple-600 text-white text-xs ' +
        'font-medium transition' :
      'px-2.5 py-1 rounded-md text-slate-700 dark:text-slate-300 ' +
        'text-xs font-medium transition';
  }
}

function openPolicyDocModal() {
  const modal = document.getElementById('policy-doc-modal');
  setPolicyModalTab('rendered');
  if (modal) {
    modal.classList.remove('hidden');
  }
}

function renderCatalogContractOverviewHtml(contract, terms) {
  const c = contract || {};
  const termList = Array.isArray(terms) ? terms : [];
  const isKo = currentLang === 'ko';
  const targetTableLabel = isKo ? '대상 테이블:' :
    'Target Table:';

  const termCardsHtml = termList
      .map((term) => {
        const sqlMap = term.sql_mapping || {};
        return [
          '<div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 ' +
            'space-y-1.5">',
          '<div class="flex flex-wrap items-center justify-between gap-2">',
          '<div class="flex items-center gap-2">',
          '<code class="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 ' +
            'border border-indigo-200 font-mono text-xs font-bold">' +
            `${escapeHtml(term.term_id)}</code>`,
          '<span class="font-semibold text-slate-900">' +
            `${escapeHtml(term.display_name)}</span>`,
          '</div>',
          '<span class="text-[11px] px-2 py-0.5 rounded bg-white border ' +
            'border-slate-200 text-slate-600 font-mono">' +
            `${escapeHtml(term.category)}</span>`,
          '</div>',
          '<p class="text-xs text-slate-700">' +
            `${escapeHtml(term.description)}</p>`,
          '<div class="pt-1 text-[11px] font-mono text-slate-600 flex ' +
            'flex-col gap-1">',
          `<div><span class="font-semibold text-slate-700">` +
            `${escapeHtml(targetTableLabel)}` +
            '</span> <code class="text-teal-700">' +
            `${escapeHtml(sqlMap.table || '')}</code></div>`,
          '<div class="p-2 rounded bg-white border border-slate-200 ' +
            'text-slate-800 overflow-x-auto whitespace-pre">' +
            `${escapeHtml(sqlMap.expression || '')}</div>`,
          '</div>',
          '</div>',
        ].join('');
      })
      .join('');

  if (isKo) {
    return [
      '<div class="grid grid-cols-1 md:grid-cols-2 gap-3">',
      '<div class="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-200 ' +
        'space-y-1.5">',
      '<h4 class="text-xs font-bold text-indigo-950 uppercase ' +
        'tracking-wider">개념 및 목적</h4>',
      '<p class="text-xs text-slate-700 leading-relaxed">' +
        '<strong>Knowledge Catalog 시맨틱 계약</strong>' +
        '은 비즈니스 지표 정의를 LLM ' +
        '프롬프트에서 분리합니다.' +
        ' Knowledge Catalog가 공식 주문 상태 ' +
        '(<code class="font-mono text-indigo-800">' +
        `${escapeHtml(c.eligible_order_status || 'Complete')}</code>, ` +
        '<code class="font-mono text-indigo-800">' +
        `${escapeHtml(c.returned_status || 'Returned')}</code>), 롤링` +
        ' 윈도우 (<code class="font-mono text-indigo-800">' +
        `${escapeHtml(c.rolling_window_days ?? 100)} days</code>) 및 ` +
        '등급 (<code class="font-mono text-indigo-800">' +
        `${escapeHtml(c.standard_tier || 'STANDARD')}</code> vs. ` +
        '<code class="font-mono text-indigo-800">' +
        `${escapeHtml(c.vip_tier || 'VIP')}</code>)을 관리합` +
        '니다.</p>',
      '</div>',
      '<div class="p-3.5 rounded-xl bg-emerald-50/60 border ' +
        'border-emerald-200 space-y-1.5">',
      '<h4 class="text-xs font-bold text-emerald-950 uppercase ' +
        'tracking-wider">컴포넌트 연동 방식' +
        '</h4>',
      '<ul class="list-disc pl-4 space-y-1 text-xs text-slate-700">',
      '<li><strong>Step 2 (resolve_catalog_contract):</strong> Knowledge ' +
        'Catalog (<code class="font-mono">soa-business-glossary</code>, ' +
        '5분 TTL 캐시)에서 거버넌스 ' +
        '계약을 조회합니다.</li>',
      '<li><strong>Step 3 (Cloud Spanner OperationalContextGraph):</strong> ' +
        '<code class="font-mono">@standard_tier</code>, ' +
        '<code class="font-mono">@vip_tier</code>, ' +
        '<code class="font-mono">@returned_status</code>, ' +
        '<code class="font-mono">@rolling_window_days</code> 파라' +
        '미터를 ISO GQL 쿼리에 바인딩' +
        '합니다.</li>',
      '<li><strong>Step 4 (Cloud Spanner DML &amp; BigQuery Lineage):' +
        '</strong> Spanner 트랜잭션 잠금 하에서 ' +
        '<code class="font-mono">status == eligible_order_status</code>를' +
        ' 검증하고 BigQuery <code class="font-mono">' +
        'soa_action_lineage.policy_evaluations</code>에 <code ' +
        'class="font-mono">catalog_term_id</code>를 기록합' +
        '니다.</li>',
      '</ul>',
      '</div>',
      '</div>',
      '<div class="space-y-2 pt-1">',
      '<h4 class="text-xs font-bold text-slate-900 uppercase tracking-wider">' +
        '거버넌스 비즈니스 용어 ' +
        '(soa-business-glossary)</h4>',
      `<div class="space-y-2.5">${termCardsHtml}</div>`,
      '</div>',
    ].join('');
  }

  return [
    '<div class="grid grid-cols-1 md:grid-cols-2 gap-3">',
    '<div class="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-200 ' +
      'space-y-1.5">',
    '<h4 class="text-xs font-bold text-indigo-950 uppercase tracking-wider">' +
      'What It Is &amp; Purpose</h4>',
    '<p class="text-xs text-slate-700 leading-relaxed">' +
      'The <strong>Knowledge Catalog Semantic Contract</strong> decouples ' +
      'business metric definitions from LLM prompts. Instead of letting an ' +
      'LLM guess what constitutes an eligible order, a 100-day return window,' +
      ' or a VIP loyalty tier, Knowledge Catalog governs the authoritative ' +
      'status literals (<code class="font-mono text-indigo-800">' +
      `${escapeHtml(c.eligible_order_status || 'Complete')}</code>, ` +
      '<code class="font-mono text-indigo-800">' +
      `${escapeHtml(c.returned_status || 'Returned')}</code>), rolling ` +
      'window (<code class="font-mono text-indigo-800">' +
      `${escapeHtml(c.rolling_window_days ?? 100)} days</code>), and tier ` +
      'classifications (<code class="font-mono text-indigo-800">' +
      `${escapeHtml(c.standard_tier || 'STANDARD')}</code> vs. ` +
      '<code class="font-mono text-indigo-800">' +
      `${escapeHtml(c.vip_tier || 'VIP')}</code>).</p>`,
    '</div>',
    '<div class="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-200 ' +
      'space-y-1.5">',
    '<h4 class="text-xs font-bold text-emerald-950 uppercase tracking-wider">' +
      'How It Works With Other Components</h4>',
    '<ul class="list-disc pl-4 space-y-1 text-xs text-slate-700">',
    '<li><strong>Step 2 (resolve_catalog_contract):</strong> Fetches the ' +
      'governed contract from Knowledge Catalog (<code class="font-mono">' +
      'soa-business-glossary</code>, 5-min TTL cache with fallback to ' +
      '<code class="font-mono">business_glossary.json</code>).</li>',
    '<li><strong>Step 3 (Cloud Spanner OperationalContextGraph):</strong> ' +
      'Binds <code class="font-mono">@standard_tier</code>, ' +
      '<code class="font-mono">@vip_tier</code>, ' +
      '<code class="font-mono">@returned_status</code>, and ' +
      '<code class="font-mono">@rolling_window_days</code> directly into the ' +
      'parameterized ISO GQL query.</li>',
    '<li><strong>Step 4 (Cloud Spanner DML &amp; BigQuery Lineage):</strong> ' +
      'Verifies <code class="font-mono">status == eligible_order_status' +
      '</code> under the Spanner transaction lock and records the governing ' +
      '<code class="font-mono">catalog_term_id</code> in BigQuery ' +
      '<code class="font-mono">soa_action_lineage.policy_evaluations</code>.' +
      '</li>',
    '</ul>',
    '</div>',
    '</div>',
    '<div class="space-y-2 pt-1">',
    '<h4 class="text-xs font-bold text-slate-900 uppercase tracking-wider">' +
      'Governed Business Glossary Terms (soa-business-glossary)</h4>',
    `<div class="space-y-2.5">${termCardsHtml}</div>`,
    '</div>',
  ].join('');
}

function setCatalogModalTab(mode) {
  const overviewView = document.getElementById(
      'catalog-contract-overview-view',
  );
  const rawView = document.getElementById('catalog-contract-raw-view');
  const overviewBtn = document.getElementById('catalog-tab-overview');
  const rawBtn = document.getElementById('catalog-tab-raw');
  const isRaw = mode === 'raw';
  if (overviewView) {
    overviewView.classList.toggle('hidden', isRaw);
  }
  if (rawView) {
    rawView.classList.toggle('hidden', !isRaw);
  }
  if (overviewBtn) {
    overviewBtn.className = !isRaw ?
      'px-2.5 py-1 rounded-md bg-indigo-600 text-white text-xs ' +
        'font-medium transition' :
      'px-2.5 py-1 rounded-md text-slate-700 dark:text-slate-300 ' +
        'text-xs font-medium transition';
  }
  if (rawBtn) {
    rawBtn.className = isRaw ?
      'px-2.5 py-1 rounded-md bg-indigo-600 text-white text-xs ' +
        'font-medium transition' :
      'px-2.5 py-1 rounded-md text-slate-700 dark:text-slate-300 ' +
        'text-xs font-medium transition';
  }
}

function openCatalogContractModal() {
  const modal = document.getElementById('catalog-contract-modal');
  setCatalogModalTab('overview');
  if (modal) {
    modal.classList.remove('hidden');
  }
}

function closeCatalogContractModal() {
  const modal = document.getElementById('catalog-contract-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

function closePolicyDocModal() {
  const modal = document.getElementById('policy-doc-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

async function loadGovernance() {
  const response = await fetch('/api/governance');
  const data = await response.json();
  cachedGovernanceData = data;
  const contractEl = document.getElementById('catalog-contract-view');
  const triplesEl = document.getElementById('u2g-triples-view');
  const catalogOverviewEl = document.getElementById(
      'catalog-contract-overview-view',
  );
  const catalogRawEl = document.getElementById('catalog-contract-raw-view');
  const renderedPolicyEl = document.getElementById('policy-doc-rendered-view');
  const rawPolicyEl = document.getElementById('policy-doc-raw-view');
  const modeBadge = document.getElementById('bq-mode-badge');
  if (contractEl) {
    contractEl.innerHTML = highlightJson(data.catalog_contract);
  }
  if (triplesEl) {
    triplesEl.innerHTML = highlightJson(data.u2g_triples);
  }
  if (catalogOverviewEl) {
    catalogOverviewEl.innerHTML = renderCatalogContractOverviewHtml(
        data.catalog_contract,
        data.glossary_terms,
    );
  }
  if (catalogRawEl) {
    catalogRawEl.innerHTML = highlightJson({
      catalog_contract: data.catalog_contract,
      terms: data.glossary_terms || [],
    });
  }
  if (data.policy_document_markdown) {
    if (renderedPolicyEl) {
      renderedPolicyEl.innerHTML = renderPolicyMarkdownHtml(
          data.policy_document_markdown,
      );
    }
    if (rawPolicyEl) {
      rawPolicyEl.textContent = data.policy_document_markdown;
    }
  }
  if (data.runtime_config) {
    spannerConnectionId =
      data.runtime_config.spanner_connection_id || spannerConnectionId;
    if (modeBadge) {
      modeBadge.textContent =
        `bq_mode: ${data.runtime_config.bq_graph_mode || 'gql'}`;
    }
  }
}

async function runWorkbenchQuery() {
  const editor = document.getElementById('query-editor');
  const statusEl = document.getElementById('query-status');
  const wrapper = document.getElementById('query-results-wrapper');
  if (!editor || !wrapper) return;
  const strings = t();

  const endpoint =
    activeTab === 'spanner' ? '/api/query/spanner' : '/api/query/bigquery';
  if (statusEl) statusEl.textContent = strings.runningQueryStatus;

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: editor.value}),
  });
  const result = await response.json();
  if (!response.ok) {
    if (statusEl) statusEl.textContent = strings.errorStatus;
    wrapper.innerHTML = [
      '<div class="text-xs text-rose-700 dark:text-rose-300 font-mono">',
      escapeHtml(result.detail || 'Query failed'),
      '</div>',
    ].join('');
    return;
  }

  const modeNote = result.execution_mode ?
    ` | mode: ${result.execution_mode}` :
    '';
  if (statusEl) {
    statusEl.textContent =
      `${strings.rowsPrefix} ${(result.rows || []).length} | ` +
      `${result.latency_ms} ms` +
      modeNote;
  }

  const cols = result.columns || [];
  const rows = result.rows || [];
  if (cols.length === 0) {
    wrapper.innerHTML = [
      '<p class="text-xs text-slate-500 dark:text-slate-400">',
      `${escapeHtml(strings.queryZeroRows)}</p>`,
    ].join('');
    return;
  }

  const headerHtml = cols
      .map(
          (col) => [
            '<th class="px-2.5 py-1.5 text-left font-mono text-[11px]',
            ' text-blue-700 dark:text-blue-300 border-b border-slate-200',
            ' dark:border-slate-800">',
            escapeHtml(col),
            '</th>',
          ].join(''),
      )
      .join('');
  const bodyHtml = rows
      .map((row) => {
        const cells = cols
            .map(
                (col) => [
                  '<td class="px-2.5 py-1.5 font-mono text-[11px]',
                  ' text-slate-800 dark:text-slate-200 border-b',
                  ' border-slate-200 dark:border-slate-900">',
                  escapeHtml(row[col]),
                  '</td>',
                ].join(''),
            )
            .join('');
        return `<tr>${cells}</tr>`;
      })
      .join('');

  wrapper.innerHTML = [
    '<table class="w-full border-collapse">',
    `<thead><tr>${headerHtml}</tr></thead>`,
    `<tbody>${bodyHtml}</tbody>`,
    '</table>',
  ].join('');
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
    applyConsoleLanguage();
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

  try {
    window.localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
    window.localStorage.removeItem(PENDING_ORDER_STORAGE_KEY);
    window.localStorage.removeItem(ACTIVE_USER_STORAGE_KEY);
  } catch {
    // Ignore storage errors in private browsing mode
  }
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
  selectedTraceId = 'trace-a1b2c3d4';
  await loadTraces();
  renderPresetButtons();

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

async function initConsoleApp() {
  document.documentElement.classList.remove('dark');
  applyConsoleLanguage();
  await loadGovernance();
  await loadTraces();
  renderPresetButtons();

  document.querySelectorAll('.workbench-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeTab = btn.getAttribute('data-tab') || 'spanner';
      activePresetIdx = 0;
      document.querySelectorAll('.workbench-tab').forEach((other) => {
        const isCurrent = other.getAttribute('data-tab') === activeTab;
        other.className = isCurrent ?
          'workbench-tab px-3 py-1.5 rounded-md bg-blue-600 text-white ' +
            'text-xs font-medium' :
          'workbench-tab px-3 py-1.5 rounded-md bg-slate-100 ' +
            'text-slate-700 border border-slate-300 dark:bg-slate-800 ' +
            'dark:text-slate-200 dark:border-slate-700 text-xs font-medium';
      });
      renderPresetButtons();
    });
  });

  const editor = document.getElementById('query-editor');
  const highlightEl = document.getElementById('query-highlight-view');
  if (editor && highlightEl) {
    editor.addEventListener('input', syncQueryHighlight);
    editor.addEventListener('scroll', () => {
      highlightEl.scrollTop = editor.scrollTop;
      highlightEl.scrollLeft = editor.scrollLeft;
    });
  }

  const runBtn = document.getElementById('run-query-btn');
  if (runBtn) {
    runBtn.addEventListener('click', runWorkbenchQuery);
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

  const previewCatalogBtn = document.getElementById(
      'preview-catalog-contract-btn',
  );
  if (previewCatalogBtn) {
    previewCatalogBtn.addEventListener('click', () => {
      openCatalogContractModal();
    });
  }

  const closeCatalogBtn = document.getElementById(
      'close-catalog-contract-modal-btn',
  );
  if (closeCatalogBtn) {
    closeCatalogBtn.addEventListener('click', () => {
      closeCatalogContractModal();
    });
  }

  const closeCatalogFooterBtn = document.getElementById(
      'close-catalog-contract-footer-btn',
  );
  if (closeCatalogFooterBtn) {
    closeCatalogFooterBtn.addEventListener('click', () => {
      closeCatalogContractModal();
    });
  }

  const catalogTabOverview = document.getElementById('catalog-tab-overview');
  if (catalogTabOverview) {
    catalogTabOverview.addEventListener('click', () => {
      setCatalogModalTab('overview');
    });
  }

  const catalogTabRaw = document.getElementById('catalog-tab-raw');
  if (catalogTabRaw) {
    catalogTabRaw.addEventListener('click', () => {
      setCatalogModalTab('raw');
    });
  }

  const catalogModal = document.getElementById('catalog-contract-modal');
  if (catalogModal) {
    catalogModal.addEventListener('click', (evt) => {
      if (evt.target === catalogModal) {
        closeCatalogContractModal();
      }
    });
  }

  const previewPolicyBtn = document.getElementById('preview-policy-doc-btn');
  if (previewPolicyBtn) {
    previewPolicyBtn.addEventListener('click', () => {
      openPolicyDocModal();
    });
  }

  const closePolicyBtn = document.getElementById('close-policy-doc-modal-btn');
  if (closePolicyBtn) {
    closePolicyBtn.addEventListener('click', () => {
      closePolicyDocModal();
    });
  }

  const closePolicyFooterBtn = document.getElementById(
      'close-policy-doc-footer-btn',
  );
  if (closePolicyFooterBtn) {
    closePolicyFooterBtn.addEventListener('click', () => {
      closePolicyDocModal();
    });
  }

  const policyTabRendered = document.getElementById('policy-tab-rendered');
  if (policyTabRendered) {
    policyTabRendered.addEventListener('click', () => {
      setPolicyModalTab('rendered');
    });
  }

  const policyTabRaw = document.getElementById('policy-tab-raw');
  if (policyTabRaw) {
    policyTabRaw.addEventListener('click', () => {
      setPolicyModalTab('raw');
    });
  }

  const policyModal = document.getElementById('policy-doc-modal');
  if (policyModal) {
    policyModal.addEventListener('click', (evt) => {
      if (evt.target === policyModal) {
        closePolicyDocModal();
      }
    });
  }

  document.addEventListener('keydown', (evt) => {
    if (evt.key === 'Escape') {
      closeCatalogContractModal();
      closePolicyDocModal();
    }
  });
}

document.addEventListener('DOMContentLoaded', initConsoleApp);
