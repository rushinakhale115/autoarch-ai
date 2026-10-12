import io
import pandas as pd
from .database import connect, audit

TABLES={'Components':'components','Interfaces':'interfaces','Dependencies':'dependencies','Findings':'findings','Documents':'documents'}
def report_data(project_id):
    with connect() as con:
        return {name:pd.read_sql_query(f'SELECT * FROM {table} WHERE project_id=?',con,params=(project_id,)) for name,table in TABLES.items()}
def export_xlsx(project_id):
    data=report_data(project_id); out=io.BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as writer:
        for name,df in data.items(): df.to_excel(writer,sheet_name=name,index=False)
    audit(project_id,'report_export','xlsx')
    return out.getvalue()
def export_csv(df): return df.to_csv(index=False).encode('utf-8-sig')
