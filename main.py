from fastapi import FastAPI, HTTPException
import mysql.connector
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Database connection settings
DB_CONFIG = {
    "host": "localhost",  # Change if using a remote DB
    "user": "root",       # Update with actual username
    "password": "",       # Update with actual password
    "database": "mydatabase" #"salburtechnology_fmb"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# API to get all distributors with thaali count
@app.get("/distributors", response_model=List[dict])
def get_distributors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT users.full_name AS distributor_name, 
               COUNT(*) AS total_thaalis 
        FROM users 
        JOIN thaali_registrations ON users.id = thaali_registrations.distributor_id 
        GROUP BY users.full_name;
        """
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        cursor.close()
        conn.close()

        # Ensure structured response
        return [{"distributor_name": row["distributor_name"], "total_thaalis": row["total_thaalis"]} for row in result]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DistributorRequest(BaseModel):
    distributor_id: int
    check_date: str = None  # Optional, defaults to current date if not provided

@app.post("/distributors/thaali-stats", response_model=dict)
def get_distributor_thaali_stats(request: DistributorRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get distributor name and total thaalis
        basic_query = """
        SELECT
            users.full_name AS distributor_name,
            COUNT(*) AS total_thaalis
        FROM
            users
        JOIN
            thaali_registrations ON users.id = thaali_registrations.distributor_id
        WHERE
            thaali_registrations.distributor_id = %s
        GROUP BY
            users.id, users.full_name;
        """
        cursor.execute(basic_query, (request.distributor_id,))
        basic_result = cursor.fetchone()
        
        if not basic_result:
            raise HTTPException(status_code=404, detail="Distributor not found")
        
        # Get category breakdown
        category_query = """
        SELECT 
            thaali_categories.name AS category_name, 
            COUNT(*) AS category_count 
        FROM 
            thaali_registrations
        JOIN 
            thaali_categories ON thaali_categories.id = thaali_registrations.thaali_category_id 
        WHERE 
            thaali_registrations.distributor_id = %s 
        GROUP BY 
            thaali_categories.name;
        """
        cursor.execute(category_query, (request.distributor_id,))
        category_results = cursor.fetchall()
        
        # Get stopped thaalis
        check_date = request.check_date if request.check_date else "CURRENT_DATE()"
        if check_date != "CURRENT_DATE()":
            stopped_query = """
            SELECT
                COUNT(*) AS stopped_thaalis
            FROM
                thaali_registrations
            JOIN
                stop_thaalis ON thaali_registrations.thaali_id = stop_thaalis.thaali_id
            WHERE
                thaali_registrations.distributor_id = %s
                AND %s BETWEEN stop_thaalis.from_date AND stop_thaalis.to_date
            """
            cursor.execute(stopped_query, (request.distributor_id, check_date))
        else:
            stopped_query = """
            SELECT
                COUNT(*) AS stopped_thaalis
            FROM
                thaali_registrations
            JOIN
                stop_thaalis ON thaali_registrations.thaali_id = stop_thaalis.thaali_id
            WHERE
                thaali_registrations.distributor_id = %s
                AND CURRENT_DATE() BETWEEN stop_thaalis.from_date AND stop_thaalis.to_date
            """
            cursor.execute(stopped_query, (request.distributor_id,))
            
        stopped_result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Calculate unique categories count
        unique_categories = len(category_results)
        
        # Combine all results into one response
        response = {
            "distributor_name": basic_result["distributor_name"],
            "total_thaalis": basic_result["total_thaalis"],
            "unique_thaali_categories": unique_categories,
            "category_breakdown": category_results,
            "stopped_thaalis": stopped_result["stopped_thaalis"] if stopped_result and stopped_result["stopped_thaalis"] else 0
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
