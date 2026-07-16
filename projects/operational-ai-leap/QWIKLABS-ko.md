# Zero ETL for Operational AI: The Operational AI Leap

## 개요 (Overview)

The Operational AI Leap 실습은 데이터 사이언티스트와 ML 엔지니어가 실시간 벡터
검색(Vector search) 및 생성형 LLM 추론(Inference)을 데이터베이스 엔진 내부에서
직접 실행할 수 있도록 지원하는 최신 아키텍처 패러다임을 안내합니다. **Google
Colab Enterprise** 를 실시간 **AlloyDB** 데이터에 직접 연결하고
페더레이션(Zero-copy federation)을 통해 **BigQuery** 데이터 레이크와
조인함으로써, _데이터 이동 및 복제 비용 없이_ 단 몇 시간 만에 엔터프라이즈급 AI
추천 어시스턴트를 배포하는 과정을 체험할 수 있습니다.

- **Zero-ETL 아키텍처 (Zero-ETL Architecture)** : ML 개발 환경을 실시간 운영
  데이터베이스에 직접 연결하여 복잡한 ETL 파이프라인을 제거합니다.
- **데이터베이스 내장 생성형 AI (In-Database Generative AI)** : 안전한 IAM
  통합을 통해 데이터베이스 SQL 내부에서 직접 Gemini LLM 엔드포인트를 호출합니다.
- **멀티 인덱스 최적화 (Multi-Index Optimization)** : Dense Vector, Sparse
  Vector, Full-Text 검색 인덱스를 하나의 통합된 쿼리 실행 계획으로 융합합니다.
- **레이크하우스 페더레이션 (Lakehouse Federation)** : 데이터를 복사하거나
  이동하지 않고 실시간 데이터베이스와 BigQuery 데이터 레이크 간에 Zero-Copy SQL
  조인을 실행합니다.
- **연산 격리 및 분리 (Compute Isolation)** : 대용량 AI 및 분석 워크로드를
  동적으로 확장되는 읽기 전용 풀(Read Pool)로 오프로드합니다.

본 실습은 핵심 OLTP 애플리케이션의 트랜잭션 성능을 완벽하게 보호하면서도, AI
배포 주기를 _수개월에서 수시간으로_ 단축할 수 있음을 증명합니다.

---

## 실습 준비사항 (What You'll Need)

본 실습을 완료하기 위해 다음 사항이 필요합니다:

- 표준 인터넷 브라우저에 대한 액세스 ( _Chrome 브라우저 권장_ ).
- **시간 (Time)** : Qwiklabs 좌측 패널에 표시된 실습 **소요 시간 (Completion
  time)** 을 확인하세요. 이는 모든 단계를 완료하는 데 필요한 예상 시간입니다.
  실습을 끝까지 마칠 수 있도록 충분한 시간을 확보하세요. 실습을 시작한 후에는
  일시정지하고 나중에 이어할 수 없으며, _실습을 시작할 때마다 항상 Step 1부터
  다시 진행해야 합니다_.
- 별도의 개인 **Google Cloud Platform** 계정이나 프로젝트가 필요하지 않습니다.
  본 실습을 위해 사전 프로비저닝된 임시 Google Cloud 계정, 프로젝트 및 관련
  인프라 자원이 제공됩니다.
- 본인 소유의 개인 GCP 계정이 이미 있더라도, _본 실습에서는 절대 사용하지
  마세요_.
- 실습 도중 Google Cloud Console 로그인 화면이 나타나면, _반드시 본 실습에서
  제공한 임시 학생 계정만 사용하세요_. 이를 통해 개인 GCP 계정에 예기치 않은
  과금이 발생하거나 실습 자원이 충돌하는 것을 방지할 수 있습니다.
- Qwiklabs 실습을 진행할 때는 Chrome 브라우저의 새 **시크릿 창 (Incognito
  window)** 또는 별도의 브라우저를 사용하세요. 또는 실습을 시작하기 전에 다른
  모든 Google 및 Gmail 계정에서 로그아웃하세요.

---

## 실습 시작 (Start Your Lab)

준비가 완료되면 **Start Lab** 버튼을 클릭합니다. 화면 상단의 상태 바를 통해 실습
프로비저닝 진행 상황을 확인할 수 있습니다.

_Important: 이 시간 동안 어떤 작업이 진행되나요?_ Qwiklabs가 실습생을 대신하여
백그라운드에서 Google Cloud 계정, 프로젝트, 핵심 인프라 자원, 그리고 실습 제어에
필요한 IAM 권한을 자동으로 프로비저닝합니다. 즉, 실습생이 수동으로 프로젝트를
설정하고 처음부터 인프라를 구축하는 데 시간을 낭비하는 대신, 자원 생성이
완료되는 즉시 핵심 AI 실습 학습에 집중할 수 있습니다.

---

## Google Cloud Console 로그인 (Sign In to Google Cloud Console)

### 실습용 GCP 사용자 이름 및 비밀번호 확인

실습 자원 및 콘솔에 접속하려면 Qwiklabs 안내 패널에서 **Connection Details**
패널을 찾으세요. 이곳에서 **Google Cloud Platform** 에 로그인할 때 사용할 계정
ID와 비밀번호를 확인할 수 있습니다. 기타 자원 ID나 연결 정보가 제공되는 경우
역시 이 패널에 표시됩니다.

### 시크릿 창을 활용한 콘솔 접속

1.  Qwiklabs가 열려 있는 브라우저 창( _가급적 시크릿 창 권장_ ) 또는 실습 전용
    브라우저에서 **Connection Details** 패널의 **Username** 을 복사한 후 **Open
    Google Console** 버튼을 클릭합니다.
1.  메시지가 표시되면 복사한 **Username** 과 **Password** 를 차례로 입력합니다.
1.  이용약관(Terms and conditions)에 동의합니다.
1.  본 실습을 위해 한시적으로 제공되는 임시 계정이므로, _복구 옵션(Recovery
    options)을 추가하거나 무료 체험판(Free trials)에 등록하지 마세요_.

_Note: Google Cloud Platform 로고 옆 상단 좌측의 탐색 메뉴 버튼을 클릭하여
Google Cloud의 제품 및 서비스 전체 목록을 확인할 수 있습니다._

---

## 실습 환경 준비 상태 검증 (Lab Environment Readiness)

**The Operational AI Leap** Qwiklabs 실습 환경에 오신 것을 환영합니다!

본 실습에서는 세션을 시작할 때 모든 핵심 인프라와 데이터 사전 준비 작업이
_자동으로 프로비저닝 및 검증_되었습니다. 따라서 별도의 Terraform 명령어, 데이터
파이프라인 또는 데이터베이스 데이터 적재 스크립트를 수동으로 실행하실 필요가
없습니다.

- **AlloyDB for PostgreSQL** : 실시간 eCommerce 상품 카탈로그( _1,000개 이상의
  검증된 레코드_ )가 사전 적재되어 있으며, 병렬로 구축된 최적화된 벡터 검색
  인덱스( `ScaNN` , `HNSW` , `GIN` )를 바탕으로 즉시 Zero-ETL 쿼리를 실행할 수
  있습니다.
- **Cymbal Shops Demo Application** : Cloud Run에 호스팅된 실시간 웹 쇼핑몰
  애플리케이션입니다.
- **BigQuery Data Lake** : 과거 주문 및 트랜잭션 데이터( `thelook_ecommerce` )가
  크로스 리전(Cross-region) 페더레이션으로 복제되어 있습니다.
- **Colab Enterprise Runtime Template** : 사전 생성되어 비공개 데이터베이스 VPC(
  `demo-vpc` )와 안전하게 피어링되어 있습니다.

---

## Step 1: 실시간 접속 정보 및 출력값 확인 (Locate Your Lab Credentials & Outputs)

### Step 1.1: Student Visible Outputs 패널 찾기

임시 학생 계정으로 **Google Cloud Console** 에 로그인한 후, 잠시 Qwiklabs 화면
좌측의 안내 패널로 돌아와 **Student Visible Outputs** ( _또는 실습 세부정보_ )
섹션을 찾습니다.

### Step 1.2: 필수 실습 출력값 체크리스트

**Student Visible Outputs** 패널에서 아래에 나열된 핵심 출력값(Outputs)을 정확히
확인하고 메모해 둡니다:

- **Demo Application URL** ( `demo_app_url` ) : 실시간 Cymbal Shops 데모
  쇼핑몰을 확인할 수 있는 웹 URL입니다.
- **Colab Notebook GCS URI** ( `notebook*gcs_uri` ) : 대화형 영문 실습 노트북이
  저장된 Cloud Storage 경로입니다 ( _예:
  `gs://YOUR*PROJECT_ID/operational-ai-leap.ipynb`_ ).
- **Colab Notebook GCS URI (KR)** ( `notebook*gcs_uri_ko` ) : 한국어로 번역된
  대화형 실습 노트북이 저장된 Cloud Storage 경로입니다 ( _예:
  `gs://YOUR*PROJECT_ID/operational-ai-leap-ko.ipynb`_ ).
- **AlloyDB Password** ( `alloydb_password` ) : AlloyDB 데이터베이스 연결
  풀(Connection pool)에 사용되는 보안 비밀번호입니다.
- **GCP Project ID** ( `gcp_project_id` ) : 현재 실습에 할당된 Google Cloud
  프로젝트 ID입니다.
- **GCP Region** ( `gcp*region` ) : 현재 실습 자원 및 런타임 템플릿이 배포된
  정확한 Google Cloud 리전 명칭입니다 ( \*예: `us-central1` 또는 `us-west1`\_ ).
- **AlloyDB Cluster Name** ( `alloydb_cluster_name` ) : 사전 구성된 클러스터
  명칭으로 `stylesearch-cluster` 입니다.
- **VPC Network Name** ( `vpc_name` ) : 사전 구성된 비공개 네트워크로 `demo-vpc`
  입니다.
- **Colab Runtime Template ID** ( `colab_runtime_template_id` ) : 사전 구성된
  Agent Platform 런타임 템플릿으로 `stylesearch-colab-template` 입니다.

---

## Step 2: 실시간 쇼핑몰 애플리케이션 탐색 (Explore the Live Storefront Application)

1.  Student Visible Outputs에서 **Demo Application URL** 을 클릭하거나 브라우저
    주소창에 복사하여 이동합니다.
1.  Cymbal Shops eCommerce 카탈로그를 탐색해 보세요. 별도의 외부 ETL 복제 지연
    없이, 시맨틱 벡터 검색과 생성형 AI 추천이 상품 검색을 실시간으로 _어떻게
    구동하는지_ 확인할 수 있습니다.

---

## Step 3: 대화형 실습 노트북 실행 (Run the Companion Interactive Notebook)

데이터베이스 내장 AI 아키텍처의 작동 원리를 자세히 학습하기 위해, **Google Colab
Enterprise** 내부에서 대화형 Jupyter 노트북을 실행합니다. 영문 버전(
`operational-ai-leap.ipynb` )과 한국어 버전( `operational-ai-leap-ko.ipynb` ) 중
원하는 언어의 노트북을 선택할 수 있습니다.

### Step 3A: Colab Enterprise로 노트북 가져오기 (Import the Notebook into Colab Enterprise)

1.  Google Cloud Console 상단 검색창에서 **Colab Enterprise** 를 검색한 후 검색
    결과에서 **Colab Enterprise** 를 선택합니다.
1.  Colab Enterprise 화면 우측 상단에서 **Region** 드롭다운 선택기를 확인합니다.
    Student Visible Outputs에서 확인한 본인의 **GCP Region** ( `gcp*region` )과
    일치하는지 검증합니다 ( \*예: `us-central1` 또는 `us-west1`\_ ). 만약 다른
    리전이 선택되어 있다면, 드롭다운을 클릭하여 본인의 **GCP Region** 으로
    변경하여 런타임과 비공개 네트워크가 일치하도록 설정합니다.
1.  좌측 탐색 사이드바에서 **My Notebooks** 를 클릭합니다.
1.  페이지 상단의 **Import notebook** 버튼을 클릭합니다.
1.  **Import source** 옵션 아래에서 **Cloud Storage** 를 선택합니다.
1.  **Cloud Storage file** 입력란에서 **Browse** 버튼을 클릭하여 본인의 프로젝트
    버킷으로 이동한 후, 메모해 둔 `notebook_gcs_uri` (영문) 또는
    `notebook_gcs_uri_ko` (한국어) 경로에 위치한 실습 노트북 파일(
    `operational-ai-leap.ipynb` 또는 `operational-ai-leap-ko.ipynb` )을
    선택합니다.
1.  대화상자 하단의 **Import** 버튼을 클릭합니다. 브라우저 창에서 실습 노트북이
    직접 열립니다.

### Step 3B: 사전 프로비저닝된 런타임 템플릿에 연결 (Connect to the Pre-Provisioned Runtime Template)

노트북을 비공개 AlloyDB 데이터베이스 인스턴스에 안전하게 연결하려면, 일치하는
리전 내에 사전에 생성된 VPC 피어링 런타임 템플릿에 연결해야 합니다:

1.  가져온 노트북 화면 우측 상단에서 **Connect** 버튼 옆 연결 상태 표시기의
    드롭다운 화살표 `▾` 를 클릭합니다.
1.  드롭다운 메뉴에서 **Change runtime type** 또는 **Connect to a runtime** 을
    선택합니다.
1.  우측에 열리는 **Connect to Agent Platform Runtime** 패널에서 필요 시 본인의
    **GCP Region** ( `gcp_region` )이 맞는지 다시 한번 확인합니다.
1.  **Runtimes** 또는 **Runtime template** 드롭다운 메뉴를 클릭합니다.
1.  **Cymbal Shops Colab Template** ( `stylesearch-colab-template` )을
    선택합니다.
1.  **Network** 항목이 `demo-vpc` 로, **Subnetwork** 가 `demo-vpc-subnet` 으로
    지정되어 있는지 검증합니다.
1.  패널 하단의 **Connect** 버튼을 클릭합니다.
1.  런타임 인스턴스가 시작되고 초록색 **Connected** 상태가 표시될 때까지 잠시
    기다립니다.

### Step 3C: 실습 워크플로 실행 (Execute the Lab Workflows)

런타임 연결이 완료된 후, _모든 셀을 한꺼번에 실행하기 전에_ 아래 절차에 따라
파이프라인 연결 변수를 구성하고 순차적으로 실행합니다:

#### Step 3C.1: 연결 변수 구성 (필수 첫 번째 단계 / Required First Step)

1.  노트북 섹션 제목 `Connection Setup & Environment Configuration` 바로 아래의
    코드 셀( _약 Cell 5_ )을 찾습니다.
1.  `project_id = "your-project-id"` 를 Student Visible Outputs에서 확인한
    본인의 **GCP Project ID** ( `gcp_project_id` )로 변경합니다.
1.  `alloydb_password = "your-db-password"` 를 Student Visible Outputs에서
    확인한 본인의 **AlloyDB Password** ( `alloydb_password` )로 변경합니다.
1.  해당 셀 좌측의 실행 버튼 `▶` 을 클릭하거나 `Shift + Enter` 를 눌러 셀을
    실행합니다.

#### Step 3C.2: 나머지 파이프라인 단계 실행 (Execute Remaining Pipeline Stages)

1.  **Database Connection Pool** : 다음 셀을 실행하여 AlloyDB로 연결되는 저지연
    `asyncpg` 연결 풀을 초기화합니다 ( _0ms 복제 지연 시간_ ).
1.  **In-Database Generative AI** : 확장 프로그램 `google_ml_integration` 을
    사용하여 PostgreSQL 내부에서 네이티브로 `ai.generate()` 및 `embedding()` 을
    호출하는 SQL 쿼리를 실행합니다.
1.  **Reciprocal Rank Fusion (RRF)** : 벡터 유사도, 인덱스 `GIN` 을 통한
    Full-Text 키워드 검색, Sparse `BM25` 순위를 결합하여 통합 추천 카드를
    생성합니다.
1.  **Zero-Copy Lakehouse Federation** : `bigquery_fdw` 를 사용하여 별도의 ETL
    파이프라인 없이 BigQuery 과거 주문 데이터셋과 실시간 페더레이션 조인을
    실행합니다.

---

## 실습 종료 (End Your Lab)

실습을 완료한 후, Qwiklabs 화면 상단의 **End** 버튼을 클릭합니다. Qwiklabs가
실습에 사용된 인프라 자원을 자동으로 삭제하고 임시 계정을 정리합니다.

실습 경험을 평가할 수 있는 별점 창이 표시됩니다. 해당하는 별점을 선택하고 의견을
작성한 후 **Submit** 버튼을 클릭합니다.

_Note: 별점의 의미는 다음과 같습니다:_

- **1 star** = 매우 불만족 (Very dissatisfied)
- **2 stars** = 불만족 (Dissatisfied)
- **3 stars** = 보통 (Neutral)
- **4 stars** = 만족 (Satisfied)
- **5 stars** = 매우 만족 (Very satisfied)

의견을 제공하지 않으려면 대화상자를 닫아도 됩니다.

---

## 추가 학습 자원 (Additional Resources)

- Google Cloud 교육 및 자격증에 대한 자세한 내용은
  https://cloud.google.com/training/ 을 참조하세요.
- 더 많은 Google Cloud Platform 실습(Self-Paced Labs)을 진행하려면
  http://run.qwiklabs.com 을 방문하세요.
- 피드백, 제안 또는 수정 요청은 Qwiklabs의 **Support** 탭을 이용해 주세요.
