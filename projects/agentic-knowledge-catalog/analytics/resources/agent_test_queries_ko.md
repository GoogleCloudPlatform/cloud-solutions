# BigQuery Agent Verification Guide & Metadata Reference

본 문서는 Dataplex Catalog에 등록된 Custom Aspect인 **`sql-mapping` (SQL 매핑
룰셋)** 정의와 이를 활용하여 대화형 분석 에이전트(Text-to-SQL 모델)를 검증하기
위한 상세 가이드라인입니다.

---

## 1. Custom Aspect 스키마 및 정의

비즈니스 용어집(Glossary)의 각 용어는 단순 자연어 설명을 넘어, 에이전트가 데이터
질의 및 메타 가이드를 올바르게 수행할 수 있도록 아래 Custom Aspect 데이터를
내장하고 있습니다.

### 1.1. `sql-mapping` Aspect (SQL 매핑 룰셋)

에이전트가 자연어를 SQL로 번역할 때 오차가 없도록 테이블 및 조건 스니펫을
정의합니다.

| 필드명 (Field)   | 타입 (Type) | 필수 여부 | 설명 및 활용 방식                                                             |
| :--------------- | :---------- | :-------- | :---------------------------------------------------------------------------- |
| **`type`**       | `string`    | **Yes**   | 매핑 종류 (`SQL_Filter`, `Node_Attribute`, `SQL_Expression`, `Web_Analytics`) |
| **`table`**      | `string`    | No        | 매핑되는 원천 BigQuery 물리 테이블 (예: `thelook_ecommerce.users`)            |
| **`condition`**  | `string`    | No        | `SQL_Filter` 타입일 때 WHERE 절에 삽입할 조건 SQL 스니펫                      |
| **`expression`** | `string`    | No        | `SQL_Expression` / `Web_Analytics` 타입일 때 집계 연산에 적용할 SQL 수식      |
| **`attribute`**  | `string`    | No        | 특정 테이블의 매핑 컬럼명 (예: `traffic_source`)                              |

---

## 2. 주요 용어별 Custom Aspect 조견표

### 2.1. SQL Mapping Aspect 조견표 (`sql-mapping`)

| 용어 ID                         | 용어명 (디스플레이) | 매핑 종류 (`type`) | 타겟 테이블 (`table`)           | 등록된 매핑 규칙 (`condition` / `expression` / `attribute`)                                                                                                                                                                                                                |
| :------------------------------ | :------------------ | :----------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`vip-customer`**              | VIP 고객            | `SQL_Filter`       | `thelook_ecommerce.users`       | `condition`: `id IN (SELECT user_id FROM thelook_ecommerce.order_items GROUP BY user_id HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5)`                                                                                                                   |
| **`traffic-source`**            | 유입 경로           | `Node_Attribute`   | `thelook_ecommerce.users`       | `attribute`: `traffic_source`                                                                                                                                                                                                                                              |
| **`churned-customer`**          | 이탈 고객           | `SQL_Filter`       | `thelook_ecommerce.users`       | `condition`: `id NOT IN (SELECT DISTINCT user_id FROM thelook_ecommerce.orders WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY))`                                                                                                                   |
| **`newly-registered-customer`** | 신규 가입 고객      | `SQL_Filter`       | `thelook_ecommerce.users`       | `condition`: `created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)`                                                                                                                                                                                           |
| **`cart-abandonment-rate`**     | 장바구니 포기율     | `Web_Analytics`    | `thelook_ecommerce.events`      | `expression`: `COUNT(DISTINCT CASE WHEN event_type = 'Cart' AND session_id NOT IN (SELECT DISTINCT session_id FROM thelook_ecommerce.events WHERE event_type = 'Purchase') THEN session_id END) / COUNT(DISTINCT CASE WHEN event_type = 'Cart' THEN session_id END) * 100` |
| **`profit-margin-rate`**        | 마진율              | `SQL_Expression`   | `thelook_ecommerce.products`    | `expression`: `(retail_price - cost) / retail_price * 100`                                                                                                                                                                                                                 |
| **`returned-cancelled-items`**  | 반품/취소 건        | `SQL_Filter`       | `thelook_ecommerce.order_items` | `condition`: `status IN ('Returned', 'Cancelled')`                                                                                                                                                                                                                         |
| **`avg-shipping-lead-time`**    | 평균 배송 소요 시간 | `SQL_Expression`   | `thelook_ecommerce.orders`      | `expression`: `AVG(TIMESTAMP_DIFF(delivered_at, shipped_at, DAY))`                                                                                                                                                                                                         |
| **`return-rate`**               | 취소/반품 비율      | `SQL_Expression`   | `thelook_ecommerce.order_items` | `expression`: `COUNTIF(status IN ('Returned', 'Cancelled')) / COUNT(*) * 100`                                                                                                                                                                                              |

---

## 3. 대화형 분석 에이전트 검증 시나리오

### 3.1. Text-to-SQL 변역 검증 (Relational DB 질의)

#### Q1. [동의어 역맵핑 & SQL Filter 결합] 우수 고객 집계

- **자연어 질문:**
  `"지난 달에 주문 이력이 존재하는 우수 고객은 총 몇 명인가요?"`
- **에이전트 매핑 경로:**
    1.  `우수 고객` $\rightarrow$ `VIP 고객` (용어 ID: `vip-customer`) 매핑
    1.  `vip-customer` 에 등록된 `sql-mapping` (SQL Filter) 추출
    1.  `condition` 내용을 쿼리 내 Subquery로 주입하여 최종 필터링
- **예상 결과 SQL:**

    ```sql
    SELECT COUNT(DISTINCT u.id) AS vip_user_count
    FROM `your-project-id.thelook_ecommerce.users` u
    JOIN `your-project-id.thelook_ecommerce.orders` o ON u.id = o.user_id
    WHERE u.id IN (
      -- 💡 VIP 고객 정의 필터 삽입
      SELECT user_id
      FROM `your-project-id.thelook_ecommerce.order_items`
      GROUP BY user_id
      HAVING SUM(sale_price) >= 500 OR COUNT(DISTINCT order_id) >= 5
    )
    AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY);
    ```

#### Q2. [웹 로그 분석 & 마케팅 속성 결합] 채널별 장바구니 포기 트렌드

- **자연어 질문:**
  `"유입 마케팅 채널별로 장바구니 이탈율을 계산해서 이탈율이 높은 순으로 정렬해줘."`
- **에이전트 매핑 경로:**
    1.  `장바구니 이탈율` $\rightarrow$ `장바구니 포기율` (용어 ID:
        `cart-abandonment-rate`) 매핑
    1.  `마케팅 채널` $\rightarrow$ `유입 경로` (용어 ID: `traffic-source`) 매핑
        $\rightarrow$ `users.traffic_source` 속성 사용
    1.  `cart-abandonment-rate` 에 등록된 `expression` 수식을 기반으로 집계 쿼리
        생성
- **예상 결과 SQL:**

    ```sql
    SELECT
      u.traffic_source AS marketing_channel,
      -- 💡 장바구니 포기율 계산 공식 자동 주입
      COUNT(DISTINCT CASE WHEN e.event_type = 'Cart' AND e.session_id NOT IN (
        SELECT DISTINCT session_id
        FROM `your-project-id.thelook_ecommerce.events`
        WHERE event_type = 'Purchase'
      ) THEN e.session_id END) /
      COUNT(DISTINCT CASE WHEN e.event_type = 'Cart' THEN e.session_id END) * 100 AS cart_abandonment_rate
    FROM `your-project-id.thelook_ecommerce.events` e
    JOIN `your-project-id.thelook_ecommerce.users` u ON e.user_id = u.id
    GROUP BY marketing_channel
    ORDER BY cart_abandonment_rate DESC;
    ```

#### Q3. [복합 룰 결합] 마진율 및 환불률 분석

- **자연어 질문:**
  `"여성 의류 중에서 상품 마진이 40% 이상인 제품들의 환불률을 브랜드별로 계산해줘."`
- **에이전트 매핑 경로:**
    1.  `상품 마진` $\rightarrow$ `마진율` (용어 ID: `profit-margin-rate`)
        $\rightarrow$ `expression` 수식 추출
    1.  `환불률` $\rightarrow$ `취소/반품 비율` (용어 ID: `return-rate`)
        $\rightarrow$ `expression` 수식 추출
    1.  두 가지 수식 규칙을 하나의 SQL 문에 동시 주입 및 집계
- **예상 결과 SQL:**

    ```sql
    SELECT
      p.brand,
      -- 💡 취소/반품 비율 집계식 적용
      COUNTIF(oi.status IN ('Returned', 'Cancelled')) / COUNT(*) * 100 AS refund_rate
    FROM `your-project-id.thelook_ecommerce.order_items` oi
    JOIN `your-project-id.thelook_ecommerce.products` p ON oi.product_id = p.id
    WHERE p.category = 'Women'
      -- 💡 마진율 공식 필터링 적용
      AND ((p.retail_price - p.cost) / p.retail_price * 100) >= 40
    GROUP BY p.brand
    ORDER BY refund_rate DESC;
    ```

#### Q4. [부정 조건 및 속성 결합] 휴면 고객 유입 분포

- **자연어 질문:**
  `"휴면 고객들이 가장 많이 유입되었던 가입 경로 3가지는 무엇인가요?"`
- **에이전트 매핑 경로:**
    1.  `휴면 고객` $\rightarrow$ `이탈 고객` (용어 ID: `churned-customer`)
        $\rightarrow$ `condition` 부정 필터 적용
    1.  `가입 경로` $\rightarrow$ `유입 경로` (용어 ID: `traffic-source`)
        $\rightarrow$ `users.traffic_source`
- **예상 결과 SQL:**

    ```sql
    SELECT
      traffic_source AS signup_channel,
      COUNT(*) AS user_count
    FROM `your-project-id.thelook_ecommerce.users`
    WHERE id NOT IN (
      -- 💡 최근 90일간 주문 기록이 존재하지 않는 이탈 필터 삽입
      SELECT DISTINCT user_id
      FROM `your-project-id.thelook_ecommerce.orders`
      WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
    )
    GROUP BY signup_channel
    ORDER BY user_count DESC
    LIMIT 3;
    ```
