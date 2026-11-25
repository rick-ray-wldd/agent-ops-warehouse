{#-
  ISO-8601 text with an explicit offset ("2025-01-06T09:00:00+08:00") -> naive UTC timestamp.
  Done by hand on purpose: no ICU extension (one less download), and anything that is not exactly
  this shape, or has an impossible offset, becomes NULL so staging can reject the row.
-#}
{% macro utc_timestamp(col) -%}
case
    when regexp_full_match({{ col }}, '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}')
     and try_cast(substr({{ col }}, 21, 2) as integer) <= 14
     and try_cast(substr({{ col }}, 24, 2) as integer) < 60
    then try_cast(substr({{ col }}, 1, 19) as timestamp)
         - to_minutes(
             (case substr({{ col }}, 20, 1) when '+' then 1 else -1 end)
             * (cast(substr({{ col }}, 21, 2) as integer) * 60 + cast(substr({{ col }}, 24, 2) as integer))
           )
end
{%- endmacro %}
