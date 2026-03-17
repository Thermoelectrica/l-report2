-- Sample enum query that returns a list of values
SELECT unnest(ARRAY['option1', 'option2', 'option3', 'option4']) AS value;
