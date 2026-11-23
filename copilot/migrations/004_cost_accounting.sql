ALTER TABLE copilot.llm_calls
    ADD COLUMN input_tokens bigint,
    ADD COLUMN output_tokens bigint,
    ADD COLUMN cached_input_tokens bigint,
    ADD COLUMN cost_cny_upper numeric(18,8),
    ADD CONSTRAINT llm_usage_nonnegative CHECK (
        (input_tokens IS NULL OR input_tokens >= 0) AND
        (output_tokens IS NULL OR output_tokens >= 0) AND
        (cached_input_tokens IS NULL OR cached_input_tokens BETWEEN 0 AND input_tokens) AND
        (cost_cny_upper IS NULL OR cost_cny_upper >= 0)
    );
