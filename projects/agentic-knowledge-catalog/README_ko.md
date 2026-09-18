# Agentic Data Cloud & Knowledge Catalog 데모

이 저장소는 Google Cloud 상에 AI 대응 데이터 클라우드 인프라를 구축하고, Google
Cloud Dataplex, Gemini, BigQuery를 활용한 고급 데이터 분석 및 메타데이터
거버넌스를 실습하는 **Agentic Data Cloud 데모**용 코드와 설정을 담고 있습니다.

## 저장소 구조

프로젝트는 다음과 같은 구조로 구성되어 있습니다:

```text
.
├── main.tf                   # Qwiklabs 및 독립 실행용 루트 테라폼 인프라 구성
├── variables.tf              # 테라폼 입력 변수 정의 (Qwiklabs 필수 파라미터 포함)
├── outputs.tf                # Qwiklabs student_visible_outputs에 전달할 출력 정의
├── qwiklabs.yaml             # Qwiklabs V2 번들 명세서
├── runtime.yaml              # Qwiklabs 스크립트 런타임 정의 (Terraform 1.15.6)
├── QWIKLABS.md               # 실습 학생용 안내 매뉴얼 (영문)
├── QWIKLABS_ko.md            # 실습 학생용 안내 매뉴얼 (한글)
├── buildtest.dockerfile      # CI/CD 프리서브밋 컨테이너 빌드 & 테스트 설정
│
├── analytics/                # Python 및 Jupyter 노트북을 활용한 데이터 분석 및 AI 실습
│   ├── notebooks/            # 데이터 품질, 카탈로그, 그래프, AI 연동을 위한 대화형 노트북
│   ├── resources/            # 비즈니스 용어집 및 물리 스키마 매핑 정의 파일
│   └── pyproject.toml        # 현대적인 파이썬 의존성 관리 설정 (uv 사용)
│
└── scripts/                  # 자동화 스크립트
    └── build_qwiklabs_bundle.sh # Git 추적 파일을 Qwiklabs 배포용 ZIP 아카이브로 패키징
```

## Qwiklabs 실습 실행

본 저장소는 Terraform `1.15.6` 런타임 기반의 **Qwiklabs V2 번들 명세**를 기본
지원합니다:

1.  **인프라 자동 프로비저닝**: Qwiklabs에서 **Start Lab** 버튼을 클릭하면
    `main.tf`가 자동으로 실행되어 Google Cloud API를 활성화하고, VPC
    네트워크를 구성하며, `thelook_ecommerce` BigQuery 데이터셋 생성 및 공개
    테이블 복제를 수행하고, Colab Enterprise 런타임 템플릿과 Cloud Storage
    노트북을 자동 배치합니다.
1.  **실습 진행**: [QWIKLABS_ko.md](QWIKLABS_ko.md) (또는
    [QWIKLABS.md](QWIKLABS.md)) 안내에 따라 Cloud Storage 경로에서 Colab
    Enterprise로 노트북을 가져와 연결된 런타임 템플릿에서 분석을 진행합니다.
1.  **Qwiklabs 배포 번들 생성**: 다음 스크립트를 실행하여 배포용 ZIP 아카이브를
    패키징합니다:

```bash
./scripts/build_qwiklabs_bundle.sh
```

## 테라폼을 통한 독립 실행 (Standalone)

Qwiklabs 환경 외에서 인프라를 직접 배포할 경우:

1.  Google Cloud 인증 및 대상 프로젝트 설정:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

1.  테라폼 초기화 및 배포:

```bash
terraform init
terraform apply -var="gcp_project_id=$(gcloud config get-value project)"
```

1.  배포된 출력값을 통해 Colab Enterprise 런타임 템플릿 ID 및 Cloud Storage 버킷
    경로 확인:

```bash
terraform output
```

## Colab Enterprise에서 주피터 노트북 실행

1.  Google Cloud 콘솔에서 **Colab Enterprise**로 이동합니다.
1.  배포 리전(기본값: `us-central1`)과 콘솔 상단 리전이 일치하는지 확인합니다.
1.  `terraform output notebooks_gcs_bucket`에 표시된 Cloud Storage 버킷 경로에서
    대상 노트북을 가져옵니다.
1.  사전 생성된 Colab Enterprise 런타임 템플릿에 노트북을 연결합니다.
1.  `01`부터 `07`까지의 노트북 셀을 순차적으로 실행합니다.

## 라이선스

이 프로젝트는 Apache 2.0 라이선스를 따릅니다.
