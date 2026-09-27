CREATE DATABASE IF NOT EXISTS sales_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sales_demo;

CREATE TABLE IF NOT EXISTS customers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(160) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    country VARCHAR(80) NOT NULL,
    company VARCHAR(255) NOT NULL,
    industry VARCHAR(120) NOT NULL,
    contact_name VARCHAR(120) NOT NULL,
    status VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_customers_name (name),
    INDEX idx_customers_company (company)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_no VARCHAR(80) NOT NULL UNIQUE,
    order_date DATE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    amount DECIMAL(14, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    status VARCHAR(40) NOT NULL,
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id),
    INDEX idx_orders_customer_date (customer_id, order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS followups (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    followup_date DATE NOT NULL,
    channel VARCHAR(40) NOT NULL,
    summary TEXT NOT NULL,
    next_action TEXT NOT NULL,
    owner VARCHAR(120) NOT NULL,
    CONSTRAINT fk_followups_customer FOREIGN KEY (customer_id) REFERENCES customers(id),
    INDEX idx_followups_customer_date (customer_id, followup_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    state_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    request_id VARCHAR(64) NULL,
    role VARCHAR(20) NOT NULL,
    message_type VARCHAR(40) NOT NULL,
    content LONGTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_messages_session FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
    INDEX idx_messages_session (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tool_call_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    request_id VARCHAR(64) NULL,
    tool_name VARCHAR(120) NOT NULL,
    arguments_json JSON NOT NULL,
    result_json JSON NULL,
    status VARCHAR(40) NOT NULL,
    duration_ms INT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tool_logs_session FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
    INDEX idx_tool_logs_request (session_id, request_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    request_id VARCHAR(64) NOT NULL,
    status VARCHAR(40) NOT NULL,
    result_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_analysis_session FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
    UNIQUE KEY uq_analysis_request (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO customers (name, email, country, company, industry, contact_name, status)
VALUES
('张三科技', 'zhangsan@example.com', '中国', '张三科技有限公司', '跨境电商 SaaS', '李娜', 'VIP'),
('北辰制造', 'beichen@example.com', '中国', '北辰制造集团', '制造业', '王强', '重点客户'),
('云启教育', 'yunqi@example.com', '中国', '云启教育科技', '教育', '陈晨', '普通'),
('星河零售', 'xinghe@example.com', '中国', '星河零售集团', '零售', '李娜', 'VIP'),
('Acme Trading', 'ops@acme-trading.example', '美国', 'Acme Trading Inc.', '贸易', 'Emma Smith', '重点客户'),
('Acme Retail', 'buying@acme-retail.example', '英国', 'Acme Retail Ltd.', '零售', 'Oliver Brown', '普通'),
('Nova Outdoor', 'procurement@nova-outdoor.example', '德国', 'Nova Outdoor GmbH', '户外用品', 'Anna Weber', '重点客户'),
('Pacific Home', 'growth@pacific-home.example', '澳大利亚', 'Pacific Home Pty Ltd.', '家居', 'Liam Wilson', '普通'),
('远航物流', 'contact@yuanhang.example', '新加坡', '远航物流有限公司', '物流', '赵敏', '重点客户'),
('BluePeak Commerce', 'sales@bluepeak.example', '加拿大', 'BluePeak Commerce Inc.', '跨境电商', 'Noah Martin', '普通')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260901001', '2026-09-01', 'API Gateway Pro', 1, 88000.00, 'CNY', 'delivered'
FROM customers WHERE name = '张三科技'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260901001');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260903002', '2026-09-03', 'Usage Pack 100M', 2, 26000.00, 'CNY', 'paid'
FROM customers WHERE name = '张三科技'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260903002');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260905003', '2026-09-05', 'Workflow Suite', 1, 56000.00, 'CNY', 'delivered'
FROM customers WHERE name = '北辰制造'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260905003');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260912005', '2026-09-12', 'CRM Connector', 1, 45000.00, 'CNY', 'paid'
FROM customers WHERE name = '星河零售'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260912005');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260914006', '2026-09-14', 'Usage Pack 100M', 5, 7000.00, 'USD', 'processing'
FROM customers WHERE name = 'Acme Trading'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260914006');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260822007', '2026-08-22', 'API Gateway Pro', 2, 22000.00, 'GBP', 'delivered'
FROM customers WHERE name = 'Acme Retail'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260822007');
INSERT INTO orders (customer_id, order_no, order_date, product_name, quantity, amount, currency, status)
SELECT id, 'SO20260918008', '2026-09-18', 'CRM Connector', 1, 18000.00, 'EUR', 'paid'
FROM customers WHERE name = 'Nova Outdoor'
AND NOT EXISTS (SELECT 1 FROM orders WHERE order_no = 'SO20260918008');

INSERT INTO followups (customer_id, followup_date, channel, summary, next_action, owner)
SELECT id, '2026-09-15', 'email', '客户确认 Usage Pack 100M 的扩容需求。', '确认未来三个月调用量预测。', '李娜'
FROM customers WHERE name = '张三科技'
AND NOT EXISTS (SELECT 1 FROM followups WHERE summary LIKE '客户确认 Usage Pack 100M%');
INSERT INTO followups (customer_id, followup_date, channel, summary, next_action, owner)
SELECT id, '2026-09-18', 'online_meeting', '客户询问 API Gateway Pro 的海外节点覆盖。', '提供节点清单并安排技术回访。', '李娜'
FROM customers WHERE name = '张三科技'
AND NOT EXISTS (SELECT 1 FROM followups WHERE summary LIKE '客户询问 API Gateway Pro%');
INSERT INTO followups (customer_id, followup_date, channel, summary, next_action, owner)
SELECT id, '2026-09-16', 'phone', '跟进 Workflow Suite 项目交付验收。', '确认验收时间和遗留问题。', '王强'
FROM customers WHERE name = '北辰制造'
AND NOT EXISTS (SELECT 1 FROM followups WHERE summary LIKE '跟进 Workflow Suite%');
INSERT INTO followups (customer_id, followup_date, channel, summary, next_action, owner)
SELECT id, '2026-09-20', 'email', '确认 CRM Connector 上线时间。', '确认数据字段和同步频率。', '李娜'
FROM customers WHERE name = '星河零售'
AND NOT EXISTS (SELECT 1 FROM followups WHERE summary LIKE '确认 CRM Connector%');
INSERT INTO followups (customer_id, followup_date, channel, summary, next_action, owner)
SELECT id, '2026-09-19', 'email', '客户反馈 Usage Pack 100M 仍在评估中。', '询问采购审批时间和预算窗口。', '当前销售'
FROM customers WHERE name = 'Acme Trading'
AND NOT EXISTS (SELECT 1 FROM followups WHERE summary LIKE '客户反馈 Usage Pack 100M%');
