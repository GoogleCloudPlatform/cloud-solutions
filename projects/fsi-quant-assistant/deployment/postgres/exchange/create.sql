-- Copyright 2025 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

create schema exchange;
set search_path TO exchange;

create sequence order_book_snapshot_id_seq;

create type buy_sell as enum ('BUY', 'SELL');

create type order_type as enum ('MARKET', 'LIMIT');

create type ledger_bucket as enum ('AVAILABLE', 'LOCKED');

create type transaction_reason as enum ('DEPOSIT', 'WITHDRAWAL', 'ORDER_LOCK', 'ORDER_UNLOCK', 'TRADE', 'FEE');

create table users
(
    id        integer generated always as identity
        constraint users_pkey
            primary key,
    created   timestamp default now() not null,
    user_name varchar(128)            not null
        constraint users_user_name_key
            unique
);

create table securities
(
    id       integer generated always as identity
        constraint securities_pkey
            primary key,
    symbol   varchar(12)                                 not null
        constraint securities_symbol_key
            unique,
    currency varchar(3) default 'USD'::character varying not null,
    created  timestamp  default now()                    not null
);

create index idx_securities_symbol
    on securities (symbol);

create table orders
(
    id          bigint generated always as identity
        constraint orders_pkey
            primary key,
    created     timestamp default now()           not null,
    user_id     integer                           not null
        constraint orders_user_id_fkey
            references users
            on delete restrict,
    security_id integer                           not null
        constraint orders_security_id_fkey
            references securities
            on delete restrict,
    side        buy_sell                          not null,
    type        order_type                        not null,
    price       numeric(32, 16)
        constraint orders_price_check
            check (price > (0)::numeric),
    amount      numeric(32, 16)                   not null
        constraint orders_amount_check
            check (amount > (0)::numeric),
    status      text      default 'PENDING'::text not null,
    constraint orders_type_price_check
        check (((type = 'MARKET'::order_type) AND (price IS NULL)) OR
               ((type = 'LIMIT'::order_type) AND (price IS NOT NULL)))
);

create table offers
(
    id          bigint generated always as identity
        constraint offers_pkey
            primary key,
    created     timestamp default now() not null,
    user_id     integer                 not null
        constraint offers_user_id_fkey
            references users
            on delete restrict,
    security_id integer                 not null
        constraint offers_security_id_fkey
            references securities
            on delete restrict,
    side        buy_sell                not null,
    price       numeric(32, 16)
        constraint offers_price_check
            check (price > (0)::numeric),
    amount      numeric(32, 16)         not null
        constraint offers_amount_check
            check (amount > (0)::numeric),
    unfilled    numeric(32, 16)         not null,
    active      boolean   default true  not null,
    type        order_type              not null,
    order_id    bigint
        constraint offers_order_id_fkey
            references orders,
    constraint offers_check
        check (unfilled <= amount),
    constraint offers_type_price_check
        check (((type = 'MARKET'::order_type) AND (price IS NULL)) OR
               ((type = 'LIMIT'::order_type) AND (price IS NOT NULL)))
);

create index idx_offers_matching
    on offers (security_id, side, price, created)
    where (active = true);

create table fills
(
    id            bigint generated always as identity
        constraint fills_pkey
            primary key,
    created       timestamp       default now() not null,
    security_id   integer                       not null
        constraint fills_security_id_fkey
            references securities
            on delete restrict,
    offer_id      bigint                        not null
        constraint fills_offer_id_fkey
            references offers
            on delete restrict,
    maker_user_id integer                       not null
        constraint fills_maker_user_id_fkey
            references users
            on delete restrict,
    taker_user_id integer                       not null
        constraint fills_taker_user_id_fkey
            references users
            on delete restrict,
    price         numeric(32, 16)               not null
        constraint fills_price_check
            check (price > (0)::numeric),
    amount        numeric(32, 16)               not null
        constraint fills_amount_check
            check (amount > (0)::numeric),
    maker_fee     numeric(32, 16) default 0.0   not null,
    taker_fee     numeric(32, 16) default 0.0   not null
);

create index idx_fills_history
    on fills (security_id, created);

create index idx_orders_user
    on orders (user_id, created);

create index idx_orders_security
    on orders (security_id, created);

create table ledger
(
    id           bigint generated always as identity
        constraint ledger_pkey
            primary key,
    created      timestamp default now() not null,
    user_id      integer                 not null
        constraint ledger_user_id_fkey
            references users,
    security_id  integer                 not null
        constraint ledger_security_id_fkey
            references securities,
    bucket       ledger_bucket           not null,
    amount       numeric(32, 16)         not null,
    reason       transaction_reason      not null,
    ref_order_id bigint,
    ref_fill_id  bigint,
    description  text
);

create index idx_ledger_user_history
    on ledger (user_id, security_id, created);

create table balances
(
    user_id     integer                   not null,
    security_id integer                   not null,
    available   numeric(32, 16) default 0 not null,
    locked      numeric(32, 16) default 0 not null,
    constraint portfolios_pkey
        primary key (user_id, security_id),
    constraint balances_no_negatives
        check ((available >= (0)::numeric) AND (locked >= (0)::numeric))
);

create table order_book_snapshot
(
    snapshot_id bigint not null,
    created     timestamp default now(),
    symbol      varchar(12),
    side        text,
    price       numeric(32, 16),
    quantity    numeric,
    order_count bigint
);

create index order_book_snapshot_snapshot_id_index
    on order_book_snapshot (snapshot_id);

create view v_order_summary
            (order_id, created, user_name, symbol, side, type, status, order_price, total_qty, offer_id,
             remaining_open_qty, is_active_on_book, calculated_filled_qty)
as
SELECT o.id         AS order_id,
       o.created,
       u.user_name,
       s.symbol,
       o.side,
       o.type,
       o.status,
       o.price      AS order_price,
       o.amount     AS total_qty,
       ofr.id       AS offer_id,
       ofr.unfilled AS remaining_open_qty,
       ofr.active   AS is_active_on_book,
       CASE
           WHEN o.status = 'FILLED'::text THEN o.amount
           WHEN o.status ~~ 'REJECTED%'::text THEN 0::numeric
           WHEN o.status = 'NO_LIQUIDITY'::text THEN 0::numeric
           WHEN ofr.id IS NOT NULL THEN o.amount - ofr.unfilled
           ELSE 0::numeric
           END      AS calculated_filled_qty
FROM orders o
         JOIN users u ON o.user_id = u.id
         JOIN securities s ON o.security_id = s.id
         LEFT JOIN offers ofr ON o.id = ofr.order_id;

create view v_order_book(symbol, side, price, quantity, order_count) as
SELECT s.symbol,
       o.side,
       o.price,
       sum(o.unfilled) AS quantity,
       count(o.id)     AS order_count
FROM offers o
         JOIN securities s ON o.security_id = s.id
WHERE o.active = true
  AND o.unfilled > 0::numeric
GROUP BY s.symbol, o.side, o.price;

create view v_bbo(symbol, bid_price, bid_size, ask_price, ask_size) as
WITH ranked_levels AS (SELECT v_order_book.symbol,
                              v_order_book.side,
                              v_order_book.price,
                              v_order_book.quantity,
                              row_number() OVER (PARTITION BY v_order_book.symbol, v_order_book.side ORDER BY (
                                  CASE
                                      WHEN v_order_book.side = 'BUY'::buy_sell THEN v_order_book.price
                                      ELSE NULL::numeric
                                      END) DESC, (
                                  CASE
                                      WHEN v_order_book.side = 'SELL'::buy_sell THEN v_order_book.price
                                      ELSE NULL::numeric
                                      END)) AS rn
                       FROM v_order_book)
SELECT s.symbol,
       b.price    AS bid_price,
       b.quantity AS bid_size,
       a.price    AS ask_price,
       a.quantity AS ask_size
FROM securities s
         LEFT JOIN ranked_levels b ON s.symbol::text = b.symbol::text AND b.side = 'BUY'::buy_sell AND b.rn = 1
         LEFT JOIN ranked_levels a ON s.symbol::text = a.symbol::text AND a.side = 'SELL'::buy_sell AND a.rn = 1;

create view v_last_sale(symbol, last_price, last_size, trade_time) as
SELECT DISTINCT ON (s.symbol) s.symbol,
                              f.price   AS last_price,
                              f.amount  AS last_size,
                              f.created AS trade_time
FROM fills f
         JOIN securities s ON f.security_id = s.id
ORDER BY s.symbol, f.created DESC;

create view v_tape (fill_id, trade_time, symbol, price, amount, maker_user_id, taker_user_id, maker_fee, taker_fee) as
SELECT f.id      AS fill_id,
       f.created AS trade_time,
       s.symbol,
       f.price,
       f.amount,
       f.maker_user_id,
       f.taker_user_id,
       f.maker_fee,
       f.taker_fee
FROM fills f
         JOIN securities s ON f.security_id = s.id;

create view v_ohlc (symbol, candle_start, open_price, high_price, low_price, close_price, volume_traded, trade_count) as
SELECT s.symbol,
       date_trunc('hour'::text, f.created)             AS candle_start,
       (array_agg(f.price ORDER BY f.created))[1]      AS open_price,
       max(f.price)                                    AS high_price,
       min(f.price)                                    AS low_price,
       (array_agg(f.price ORDER BY f.created DESC))[1] AS close_price,
       sum(f.amount)                                   AS volume_traded,
       count(f.id)                                     AS trade_count
FROM fills f
         JOIN securities s ON f.security_id = s.id
GROUP BY s.symbol, (date_trunc('hour'::text, f.created));

create view v_balances(user_name, symbol, available, locked, total) as
SELECT u.user_name,
       s.symbol,
       b.available,
       b.locked,
       b.available + b.locked AS total
FROM balances b
         JOIN users u ON b.user_id = u.id
         JOIN securities s ON b.security_id = s.id
ORDER BY u.user_name, s.symbol;

create view v_money_movement
            (ledger_id, created, user_name, symbol, bucket, amount, reason, description, ref_order_id, ref_fill_id) as
SELECT l.id           AS ledger_id,
       l.created,
       u.user_name,
       s.symbol,
       l.bucket::text AS bucket,
       l.amount,
       l.reason::text AS reason,
       l.description,
       l.ref_order_id,
       l.ref_fill_id
FROM ledger l
         JOIN users u ON l.user_id = u.id
         JOIN securities s ON l.security_id = s.id
ORDER BY l.id;

create view v_order_history (order_id, created, user_name, symbol, side, type, price, amount, status) as
SELECT o.id         AS order_id,
       o.created,
       u.user_name,
       s.symbol,
       o.side::text AS side,
       o.type::text AS type,
       o.price,
       o.amount,
       o.status
FROM orders o
         JOIN users u ON o.user_id = u.id
         JOIN securities s ON o.security_id = s.id;

create view v_trading_statement
            (transaction_id, transaction_time, user_name, transaction_type, symbol, balance_category, change_amount,
             running_balance, execution_price, order_side, order_type, description, ref_order_id, ref_fill_id)
as
SELECT l.id                                                                                                                  AS transaction_id,
       l.created                                                                                                             AS transaction_time,
       u.user_name,
       l.reason::text                                                                                                        AS transaction_type,
       s.symbol,
       l.bucket::text                                                                                                        AS balance_category,
       l.amount                                                                                                              AS change_amount,
       sum(l.amount)
       OVER (PARTITION BY l.user_id, l.security_id, l.bucket ORDER BY l.id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance,
       f.price                                                                                                               AS execution_price,
       o.side::text                                                                                                          AS order_side,
       o.type::text                                                                                                          AS order_type,
       l.description,
       l.ref_order_id,
       l.ref_fill_id
FROM ledger l
         JOIN users u ON l.user_id = u.id
         JOIN securities s ON l.security_id = s.id
         LEFT JOIN fills f ON l.ref_fill_id = f.id
         LEFT JOIN orders o ON l.ref_order_id = o.id
ORDER BY l.id DESC;

create view v_order_fills
            (order_id, order_time, user_name, symbol, order_side, order_type, order_status, order_original_qty,
             order_limit_price, fill_id, fill_time, fill_qty, fill_price, fill_total_value, fee_paid)
as
SELECT o.id               AS order_id,
       o.created          AS order_time,
       u.user_name,
       s.symbol,
       o.side::text       AS order_side,
       o.type::text       AS order_type,
       o.status           AS order_status,
       o.amount           AS order_original_qty,
       o.price            AS order_limit_price,
       f.id               AS fill_id,
       f.created          AS fill_time,
       f.amount           AS fill_qty,
       f.price            AS fill_price,
       f.amount * f.price AS fill_total_value,
       CASE
           WHEN o.user_id = f.maker_user_id THEN f.maker_fee
           WHEN o.user_id = f.taker_user_id THEN f.taker_fee
           ELSE NULL::numeric
           END            AS fee_paid
FROM orders o
         JOIN users u ON o.user_id = u.id
         JOIN securities s ON o.security_id = s.id
         LEFT JOIN (SELECT DISTINCT ledger.ref_order_id,
                                    ledger.ref_fill_id
                    FROM ledger
                    WHERE ledger.reason = 'TRADE'::transaction_reason) link ON o.id = link.ref_order_id
         LEFT JOIN fills f ON link.ref_fill_id = f.id
ORDER BY o.id DESC, f.id;

create function block_crosses() returns trigger
    language plpgsql
as
$$
BEGIN
    -- We only check if the price is NOT NULL (Limit orders)
    IF NEW.price IS NOT NULL THEN
        IF check_is_crossed(NEW.security_id, NEW.side, NEW.price) THEN
            RAISE EXCEPTION 'This order would result in a crossed book.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

create trigger tr_offer_block_crosses
    before insert or update
    on offers
    for each row
execute procedure block_crosses();

create function populate_unfilled() returns trigger
    language plpgsql
as
$$
BEGIN
    -- Only auto-fill if the user/function didn't provide a specific value
    IF NEW.unfilled IS NULL THEN
        NEW.unfilled := NEW.amount;
    END IF;

    RETURN NEW;
END;
$$;

create trigger tr_offer_insert
    before insert
    on offers
    for each row
execute procedure populate_unfilled();

create function check_is_crossed(_security_id integer, _side buy_sell, _price numeric) returns boolean
    stable
    language plpgsql
as
$$
BEGIN
    IF _side = 'BUY' THEN
        RETURN EXISTS (
            SELECT 1
            FROM offers
            WHERE security_id = _security_id
              AND side = 'SELL'
              AND unfilled > 0.0
              AND active = TRUE
              AND price <= _price -- Buy price is higher than or equal to best sell
        );
    ELSE -- side is sell
        RETURN EXISTS (
            SELECT 1
            FROM offers
            WHERE security_id = _security_id
              AND side = 'BUY'
              AND unfilled > 0.0
              AND active = TRUE
              AND price >= _price -- Sell price is lower than or equal to best buy
        );
    END IF;
END;
$$;

create function get_or_create_security(_symbol character varying) returns integer
    language plpgsql
as
$$
DECLARE
    _sec_id integer;
BEGIN
    -- 1. Try to find the security ID
    SELECT id INTO _sec_id
    FROM securities
    WHERE symbol = _symbol;

    IF FOUND THEN
        RETURN _sec_id;
    END IF;

    -- 2. If not found, try to insert.
    -- We use ON CONFLICT DO NOTHING to handle race conditions
    -- where another transaction creates it between our SELECT and INSERT.
    INSERT INTO securities (symbol, currency)
    VALUES (_symbol, 'USD')
    ON CONFLICT (symbol) DO NOTHING
    RETURNING id INTO _sec_id;

    -- 3. If _sec_id is still NULL, it means a concurrent transaction
    -- inserted it and our ON CONFLICT clause triggered.
    -- We must select the ID again.
    IF _sec_id IS NULL THEN
        SELECT id INTO _sec_id
        FROM securities
        WHERE symbol = _symbol;
    END IF;

    RETURN _sec_id;
END;
$$;

create function get_or_create_user(_user_name character varying) returns integer
    language plpgsql
as
$$
DECLARE
    _u_id integer;
BEGIN
    -- 1. Try to find the user ID
    SELECT id INTO _u_id
    FROM users
    WHERE user_name = _user_name;

    IF FOUND THEN
        RETURN _u_id;
    END IF;

    -- 2. If not found, try to insert.
    -- Handle concurrent inserts with ON CONFLICT
    INSERT INTO users (user_name)
    VALUES (_user_name)
    ON CONFLICT (user_name) DO NOTHING
    RETURNING id INTO _u_id;

    -- 3. If _u_id is null (conflict occurred), fetch the ID again
    IF _u_id IS NULL THEN
        SELECT id INTO _u_id
        FROM users
        WHERE user_name = _user_name;
    END IF;

    RETURN _u_id;
END;
$$;

create function get_order_book(_symbol character varying) returns SETOF v_order_book
    stable
    SET search_path = exchange, public
    language sql
as
$$
    SELECT * FROM v_order_book
    WHERE symbol = _symbol
    ORDER BY
        side DESC, -- Groups 'sell' (Asks) first, 'buy' (Bids) second

        -- If it's a Sell, sort ASC (Lowest Price is Best)
        CASE WHEN side = 'SELL' THEN price END ASC,

        -- If it's a Buy, sort DESC (Highest Price is Best)
        CASE WHEN side = 'BUY' THEN price END DESC;
$$;

create function update_balances_cache() returns trigger
    SET search_path = exchange, public
    language plpgsql
as
$$
BEGIN
    -- 1. Optimistic Update: Try to update the existing row.
    -- This handles 99% of cases (Trading) and works fine with negative numbers
    -- because the math (balance + negative) happens inside the DB engine.
    UPDATE balances
    SET
        available = available + (CASE WHEN NEW.bucket = 'AVAILABLE' THEN NEW.amount ELSE 0 END),
        locked    = locked    + (CASE WHEN NEW.bucket = 'LOCKED'    THEN NEW.amount ELSE 0 END)
    WHERE user_id = NEW.user_id AND security_id = NEW.security_id;

    -- 2. Fallback Insert: If the row didn't exist (Found = false)
    IF NOT FOUND THEN
        -- CRITICAL CHECK: We cannot create a NEW portfolio with negative funds.
        -- This logic prevents the exact error you were seeing.
        IF NEW.amount < 0 THEN
            RAISE EXCEPTION 'Cannot create new portfolio with negative balance (User: %, Sec: %, Amt: %)',
                NEW.user_id, NEW.security_id, NEW.amount;
        END IF;

        INSERT INTO balances (user_id, security_id, available, locked)
        VALUES (
            NEW.user_id,
            NEW.security_id,
            CASE WHEN NEW.bucket = 'AVAILABLE' THEN NEW.amount ELSE 0 END,
            CASE WHEN NEW.bucket = 'LOCKED'    THEN NEW.amount ELSE 0 END
        );
    END IF;

    RETURN NEW;
END;
$$;

create trigger tr_ledger_insert
    after insert
    on ledger
    for each row
execute procedure update_balances_cache();

create function deposit_funds(_user_name character varying, _amount numeric, _symbol character varying DEFAULT 'USD'::character varying) returns jsonb
    SET search_path = exchange, public
    language plpgsql
as
$$
DECLARE
    _user_id integer;
    _security_id integer;
    _txn_id bigint;
    _new_available numeric;
    _new_locked numeric;
BEGIN
    -- 1. Validation
    IF _amount <= 0 THEN
        RETURN jsonb_build_object('status', 'ERROR', 'reason', 'Amount must be positive');
    END IF;

    -- 2. Resolve Identities (creates them if missing)
    _user_id := get_or_create_user(_user_name);
    _security_id := get_or_create_security(_symbol);

    -- 3. Insert into Ledger
    -- This specific action triggers 'tr_ledger_insert' which updates the 'balances' table
    INSERT INTO ledger (user_id, security_id, bucket, amount, reason, description)
    VALUES (_user_id, _security_id, 'AVAILABLE', _amount, 'DEPOSIT', 'Manual Deposit')
    RETURNING id INTO _txn_id;

    -- 4. Retrieve new balance state for the return object
    SELECT available, locked INTO _new_available, _new_locked
    FROM balances
    WHERE user_id = _user_id AND security_id = _security_id;

    -- 5. Return JSON response
    RETURN jsonb_build_object(
        'status', 'SUCCESS',
        'transaction_id', _txn_id,
        'user', _user_name,
        'symbol', _symbol,
        'deposited', _amount,
        'new_balance', jsonb_build_object(
            'available', _new_available,
            'locked', _new_locked,
            'total', _new_available + _new_locked
        )
    );
END;
$$;

create procedure execute_taker_sweep()
    SET search_path = exchange, public
    language plpgsql
as
$$
DECLARE
    r RECORD;

    -- CONFIGURATION ---------------------------
    _percentage   NUMERIC := 0.5; -- 50%

    -- Pool of 10 Bot Names (ALL CAPS)
    _bot_pool     TEXT[]  := ARRAY[
        'SWEEP_BOT_ALPHA', 'SWEEP_BOT_BRAVO', 'SWEEP_BOT_CHARLIE', 'SWEEP_BOT_DELTA', 'SWEEP_BOT_ECHO',
        'SWEEP_BOT_FOXTROT', 'SWEEP_BOT_GOLF', 'SWEEP_BOT_HOTEL', 'SWEEP_BOT_INDIA', 'SWEEP_BOT_JULIET'
    ];
    --------------------------------------------

    _taker_user   TEXT;
    _sweep_qty    NUMERIC;
    _taker_side   buy_sell;
    _est_cost     NUMERIC;
    _result       JSONB;
    _avg_price    NUMERIC;
BEGIN
    RAISE NOTICE 'Starting Liquidity Sweep (Targeting % of volume)...', (_percentage * 100) || '%';

    -- Iterate over every line in the order book
    FOR r IN SELECT * FROM v_order_book ORDER BY symbol, side, price LOOP

        -- 0. Pick a Random Bot for this iteration
        _taker_user := _bot_pool[ 1 + floor(random() * array_length(_bot_pool, 1))::int ];

        -- 1. Calculate the Raw Target Amount
        _sweep_qty := r.quantity * _percentage;

        -- 2. Apply Quantity Constraints
        IF r.quantity > 1 THEN
            -- If the book has real volume (>1), force our trade to be an Integer
            _sweep_qty := floor(_sweep_qty);
        ELSE
            -- If the book only has "dust" (<=1), take the full dust amount
            _sweep_qty := r.quantity;
        END IF;

        -- Safety check: Ensure we are still trading something positive
        IF _sweep_qty <= 0 THEN
            CONTINUE;
        END IF;

        -- 3. Determine Taker Side & Fund the specific Bot
        IF r.side = 'BUY' THEN
            _taker_side := 'SELL';
            PERFORM deposit_funds(_taker_user, _sweep_qty, r.symbol);

        ELSE -- Book is SELL (Asks), so we must BUY
            _taker_side := 'BUY';
            _est_cost := r.price * _sweep_qty;
            PERFORM deposit_funds(_taker_user, _est_cost, 'USD');
        END IF;

        -- 4. Execute
        RAISE NOTICE '[%] Sweeping: % % % (of available %) @ %',
            _taker_user, r.symbol, _taker_side, _sweep_qty, r.quantity, r.price;

        _result := match_order(
            _taker_user,
            r.symbol,
            _taker_side,
            'MARKET',
            NULL,
            _sweep_qty
        );

        -- 5. Report
        IF _result ->> 'status' = 'FILLED' OR _result ->> 'status' = 'PARTIAL' THEN
            SELECT sum((value->>'amount')::numeric * (value->>'price')::numeric) / sum((value->>'amount')::numeric)
            INTO _avg_price
            FROM jsonb_array_elements(_result -> 'fills');

            RAISE NOTICE ' -> SUCCESS: % shares @ avg %', _sweep_qty, round(_avg_price, 2);
        ELSE
            RAISE NOTICE ' -> FAILED: %', _result ->> 'status';
        END IF;

    END LOOP;

    RAISE NOTICE 'Sweep Complete.';
END;
$$;

create procedure create_order_book_snapshot()
    SET search_path = exchange, public
    language plpgsql
as
$$
DECLARE
    _snapshot_id BIGINT;
    _snapshot_time TIMESTAMP;
BEGIN
    _snapshot_id := nextval('order_book_snapshot_id_seq');
    _snapshot_time := now();

    insert into order_book_snapshot(snapshot_id, created, symbol, side, price, quantity, order_count)
    select _snapshot_id, _snapshot_time, symbol, side, price, quantity, order_count
    from v_order_book;

    RAISE NOTICE 'Snapshot Complete..';
END;
$$;

create function match_order(_user_name character varying, _symbol character varying, _side buy_sell, _type order_type, _price numeric, _amount numeric) returns jsonb
    SET search_path = exchange, public
    language plpgsql
as
$$
DECLARE
    -- Standard Variables
    _user_id INTEGER; _security_id INTEGER; _usd_id INTEGER; _order_id BIGINT;
    _user_balance NUMERIC; _required_amt NUMERIC;
    match RECORD; amount_taken NUMERIC; amount_remaining NUMERIC;
    cost_to_taker NUMERIC; cost_to_maker NUMERIC;
    is_market_order BOOLEAN; _status TEXT := 'PENDING'; _stp_detected BOOLEAN := FALSE;
    _fills_json JSONB; _offer_json JSONB;

    -- Error Handling Variable
    _err_constraint TEXT;

    -- Pre-calculate the side we are looking for
    _match_side buy_sell;
    _reject_reason TEXT;

    -- NEW: Variable to capture the Fill ID
    _fill_id BIGINT;
BEGIN
    -- 0. SETUP
    _user_id := get_or_create_user(_user_name);
    _security_id := get_or_create_security(_symbol);
    SELECT id INTO _usd_id FROM securities WHERE symbol = 'USD';
    is_market_order := (_type = 'MARKET');

    IF _side = 'BUY' THEN
        _match_side := 'SELL';
        _reject_reason := 'REJECTED_INSUFFICIENT_FUNDS';
    ELSE
        _match_side := 'BUY';
        _reject_reason := 'REJECTED_INSUFFICIENT_POSITION';
    END IF;

    -- 1. PRE-FLIGHT BALANCE CHECK & LOCKING
    BEGIN
        _required_amt := 0;

        IF _side = 'SELL' THEN
            SELECT available INTO _user_balance FROM balances WHERE user_id = _user_id AND security_id = _security_id;
            _required_amt := _amount;

            IF COALESCE(_user_balance, 0) < _required_amt THEN
                RETURN jsonb_build_object('status', _reject_reason);
            END IF;

            IF NOT is_market_order THEN
                INSERT INTO ledger (user_id, security_id, bucket, amount, reason, description)
                VALUES (_user_id, _security_id, 'AVAILABLE', -_required_amt, 'ORDER_LOCK', 'Lock Limit Sell'),
                       (_user_id, _security_id, 'LOCKED',    _required_amt,  'ORDER_LOCK', 'Lock Limit Sell');
            END IF;

        ELSIF _side = 'BUY' AND NOT is_market_order THEN
            SELECT available INTO _user_balance FROM balances WHERE user_id = _user_id AND security_id = _usd_id;
            _required_amt := _price * _amount;

            IF COALESCE(_user_balance, 0) < _required_amt THEN
                 RETURN jsonb_build_object('status', _reject_reason);
            END IF;

            INSERT INTO ledger (user_id, security_id, bucket, amount, reason, description)
            VALUES (_user_id, _usd_id, 'AVAILABLE', -_required_amt, 'ORDER_LOCK', 'Lock Limit Buy'),
                   (_user_id, _usd_id, 'LOCKED',    _required_amt,  'ORDER_LOCK', 'Lock Limit Buy');
        END IF;

    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS _err_constraint = CONSTRAINT_NAME;
            IF _err_constraint = 'balances_no_negatives' THEN
                RETURN jsonb_build_object('status', _reject_reason, 'reason', 'Race condition on balance lock');
            END IF;
            RAISE;
    END;

    -- 2. CREATE ORDER
    INSERT INTO orders (user_id, security_id, side, type, price, amount, status)
    VALUES (_user_id, _security_id, _side, _type, _price, _amount, 'PENDING')
    RETURNING id INTO _order_id;

    IF NOT is_market_order THEN
        UPDATE ledger SET ref_order_id = _order_id
        WHERE user_id = _user_id AND ref_order_id IS NULL AND reason = 'ORDER_LOCK';
    END IF;

    DROP TABLE IF EXISTS tmp_fills;
    DROP TABLE IF EXISTS tmp_offer;
    CREATE TEMPORARY TABLE tmp_fills (fill_id BIGINT, price NUMERIC, amount NUMERIC) ON COMMIT DROP;
    CREATE TEMPORARY TABLE tmp_offer (offer_id BIGINT, side buy_sell, price NUMERIC, amount NUMERIC) ON COMMIT DROP;
    amount_remaining := _amount;

    -- 3. MATCHING LOOP
    FOR match IN
        SELECT * FROM offers
        WHERE security_id = _security_id
          AND side = _match_side
          AND active = TRUE
          AND (is_market_order OR (_side = 'BUY' AND price <= _price) OR (_side = 'SELL' AND price >= _price))
        ORDER BY (CASE WHEN _side = 'BUY' THEN price END) ASC,
                 (CASE WHEN _side = 'SELL' THEN price END) DESC,
                 created ASC
        FOR UPDATE
    LOOP
        RAISE NOTICE 'Matching Order % against Offer % (Price: %)', _order_id, match.id, match.price;

        IF amount_remaining <= 0 THEN EXIT; END IF;

        IF match.user_id = _user_id THEN
            _stp_detected := TRUE; _status := 'REJECTED_STP'; EXIT;
        END IF;

        amount_taken := LEAST(amount_remaining, match.unfilled);
        cost_to_taker := amount_taken * match.price;
        cost_to_maker := amount_taken * match.price;

        IF is_market_order AND _side = 'BUY' THEN
            IF NOT EXISTS (SELECT 1 FROM balances WHERE user_id = _user_id AND security_id = _usd_id AND available >= cost_to_taker) THEN
                _status := 'NO_LIQUIDITY'; EXIT;
            END IF;
        END IF;

        -- EXECUTE TRADES (LEDGER)
        BEGIN
            -- 1. Create the Fill FIRST to get the ID
            INSERT INTO fills (security_id, offer_id, maker_user_id, taker_user_id, price, amount)
            VALUES (_security_id, match.id, match.user_id, _user_id, match.price, amount_taken)
            RETURNING id INTO _fill_id;

            -- 2. Insert Ledgers (Now using _fill_id)
            IF _side = 'BUY' THEN
                -- Taker (Buyer) Ledger
                INSERT INTO ledger (user_id, security_id, bucket, amount, reason, ref_order_id, ref_fill_id) VALUES
                    (_user_id, _security_id, 'AVAILABLE', amount_taken,   'TRADE', _order_id, _fill_id),
                    (_user_id, _usd_id,      (CASE WHEN is_market_order THEN 'AVAILABLE'::ledger_bucket ELSE 'LOCKED'::ledger_bucket END),
                                             -cost_to_taker, 'TRADE', _order_id, _fill_id);
            ELSE
                -- Taker (Seller) Ledger
                INSERT INTO ledger (user_id, security_id, bucket, amount, reason, ref_order_id, ref_fill_id) VALUES
                    (_user_id, _security_id, (CASE WHEN is_market_order THEN 'AVAILABLE'::ledger_bucket ELSE 'LOCKED'::ledger_bucket END),
                                             -amount_taken,  'TRADE', _order_id, _fill_id),
                    (_user_id, _usd_id,      'AVAILABLE', cost_to_maker, 'TRADE', _order_id, _fill_id);
            END IF;

            IF match.side = 'SELL' THEN
                -- Maker (Seller) Ledger
                INSERT INTO ledger (user_id, security_id, bucket, amount, reason, ref_order_id, ref_fill_id) VALUES
                    (match.user_id, _security_id, 'LOCKED',    -amount_taken,  'TRADE', match.order_id, _fill_id),
                    (match.user_id, _usd_id,      'AVAILABLE', cost_to_taker, 'TRADE', match.order_id, _fill_id);
            ELSE
                -- Maker (Buyer) Ledger
                INSERT INTO ledger (user_id, security_id, bucket, amount, reason, ref_order_id, ref_fill_id) VALUES
                    (match.user_id, _usd_id,      'LOCKED',    -cost_to_maker, 'TRADE', match.order_id, _fill_id),
                    (match.user_id, _security_id, 'AVAILABLE', amount_taken,   'TRADE', match.order_id, _fill_id);
            END IF;

        EXCEPTION
            WHEN check_violation THEN
                GET STACKED DIAGNOSTICS _err_constraint = CONSTRAINT_NAME;
                IF _err_constraint = 'balances_no_negatives' THEN
                    _status := 'REJECTED_INSUFFICIENT_FUNDS';
                    EXIT;
                END IF;
                RAISE;
        END;

        -- Update Maker Order Status
        UPDATE orders
        SET status = CASE
            WHEN (match.unfilled - amount_taken) <= 0 THEN 'FILLED'
            ELSE 'PARTIAL'
        END
        WHERE id = match.order_id;

        -- Update Maker Offer
        UPDATE offers SET unfilled = unfilled - amount_taken, active = (unfilled - amount_taken > 0)
        WHERE id = match.id;

        -- Insert into temp table for JSON response (using the correct fill ID now)
        INSERT INTO tmp_fills VALUES (_fill_id, match.price, amount_taken);
        amount_remaining := amount_remaining - amount_taken;
    END LOOP;

    -- 4. POST-MATCH (Status Logic)
    IF NOT _stp_detected AND _status NOT LIKE 'REJECTED%' THEN
        IF amount_remaining = 0 THEN _status := 'FILLED';
        ELSIF amount_remaining = _amount THEN
             IF is_market_order THEN _status := 'NO_LIQUIDITY'; ELSE _status := 'PLACED'; END IF;
        ELSE
             IF is_market_order THEN _status := 'PARTIAL_IOC'; ELSE _status := 'PARTIAL'; END IF;
        END IF;
    END IF;

    -- Handle Remaining Amount
    IF _status NOT LIKE 'REJECTED%' THEN
        IF amount_remaining > 0 AND NOT is_market_order AND NOT _stp_detected THEN
            WITH new_offer AS (
                INSERT INTO offers (user_id, security_id, side, price, amount, unfilled, active, type, order_id)
                VALUES (_user_id, _security_id, _side, _price, _amount, amount_remaining, TRUE, _type, _order_id)
                RETURNING id, side, price, amount
            )
            INSERT INTO tmp_offer SELECT * FROM new_offer;
        ELSIF amount_remaining > 0 AND NOT is_market_order AND _stp_detected THEN
             -- STP Refund
             IF _side = 'BUY' THEN
                 INSERT INTO ledger (user_id, security_id, bucket, amount, reason, description) VALUES
                 (_user_id, _usd_id, 'LOCKED', -(_price * amount_remaining), 'ORDER_UNLOCK', 'STP Refund'),
                 (_user_id, _usd_id, 'AVAILABLE', (_price * amount_remaining), 'ORDER_UNLOCK', 'STP Refund');
            ELSE
                 INSERT INTO ledger (user_id, security_id, bucket, amount, reason, description) VALUES
                 (_user_id, _security_id, 'LOCKED', -amount_remaining, 'ORDER_UNLOCK', 'STP Refund'),
                 (_user_id, _security_id, 'AVAILABLE', amount_remaining, 'ORDER_UNLOCK', 'STP Refund');
            END IF;
        END IF;
    END IF;

    UPDATE orders SET status = _status WHERE id = _order_id;
    SELECT COALESCE(jsonb_agg(to_jsonb(tf)), '[]'::jsonb) INTO _fills_json FROM tmp_fills tf;
    SELECT to_jsonb(toff) INTO _offer_json FROM tmp_offer toff LIMIT 1;

    CALL exchange.create_order_book_snapshot();
    CALL exchange.execute_taker_sweep();
    CALL exchange.create_order_book_snapshot();

    RETURN jsonb_build_object('status', _status, 'order_id', _order_id, 'fills', _fills_json, 'new_offer', _offer_json);
END;
$$;

create function clear_order_book_snapshots(_snapshot_id bigint) returns text
    SET search_path = exchange, public
    language plpgsql
as
$$
DECLARE
BEGIN
    delete
    from order_book_snapshot
    where snapshot_id <= _snapshot_id;
    return 'Success';
END;
$$;

create procedure clear_data()
    language sql
as
$$
    delete from ledger;
    delete from fills;
    delete from offers;
    delete from orders;
    delete from balances;
    delete from order_book_snapshot;
$$;

