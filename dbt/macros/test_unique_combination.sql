{#- Small stand-in for dbt_utils.unique_combination_of_columns so the project
    has no package download step. -#}
{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count() as n
from {{ model }}
group by {{ columns | join(', ') }}
having n > 1
{% endtest %}
