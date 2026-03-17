SELECT
    :text_param::text as text_param,
    :date_param::date as date_param,
    :datetime_param::timestamp as datetime_param,
    :boolean_param::boolean as boolean_param,
    :int_param::integer as int_param,
    :float_param::numeric as float_param,
    :select_param::text as select_param,
    current_timestamp as generated_at
