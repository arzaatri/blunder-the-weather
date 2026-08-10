
      create or replace view "memory"."main"."gold_ground_truth_log__dbt_int" as (
        select * from read_parquet('s3://blunder-the-weather/gold/ground_truth_log/part.parquet', union_by_name=False)
        -- if relation is empty, filter by all columns having null values
        
      );
    