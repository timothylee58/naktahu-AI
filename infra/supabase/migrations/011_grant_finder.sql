-- 011_grant_finder.sql
-- Recommended civic agent: government grant discovery for SMEs & students.

INSERT INTO agents (name, description, input_schema, plan_required, credit_cost) VALUES
(
    'grant-finder',
    'Match your business or study profile to Malaysian government grants and funding schemes.',
    '{"type":"object","properties":{"sector":{"type":"string"},"business_stage":{"type":"string"},"funding_need":{"type":"string"},"message":{"type":"string"}}}',
    'free',
    0
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    input_schema = EXCLUDED.input_schema;
