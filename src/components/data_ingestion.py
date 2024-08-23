import os
import sys
from src.exception import CustomException
from src.logger import logging


import pandas as pd
import numpy as np
from uszipcode import SearchEngine
from dataclasses import dataclass


@dataclass
class DataIngestionConfig:
    train_data_path:str = os.path.join('artifact', 'train.csv')
    test_data_path:str = os.path.join("artifact", "test.csv")
    raw_data_path:str = os.path.join("artifact", "raw_data.csv")
    
class DataIngestion:
    def __init__(self):
        self.ingestion_config = DataIngestionConfig()
    
    def initiate_data_injection(self):
        try:
            logging.info("Initiating data ingestion")
            data_path = os.path.join("notebook", "Data", "used_car_sample.csv")
            df = pd.read_csv(data_path)
            logging.info("Read the dataset as datframe")
            
            # Preliminary data cleaning
            if df.duplicated().sum() > 0: # Check for duplicate rows
                df.drop_duplicates(inplace=True)
                logging.info("Dropped duplicate rows")
            
            is_half_empty = (df.isnull().sum(axis=1) / (df.shape[1] - 1)) >= 0.5
            if is_half_empty.sum() > 0: # Check for half empty rows
                half_empty_entries = df[is_half_empty].index
                df.drop(half_empty_entries, axis=0, inplace=True)
                logging.info("Dropped half empty rows")
                
            df['year'] = pd.to_datetime(df['year']).dt.year
            df['model_name'] = df['model_name'].str.lower()
            
            # Correct improper input
            df.loc[(df['back_legroom (in)'] < 10) & (df['model_name'] == 'impreza'), 'back_legroom (in)'] = 36.5
            df.loc[(df['back_legroom (in)'] < 10) & (df['model_name'] == 'wrangler'), 'back_legroom (in)'] = 35.3
            df.loc[(df['make_name'] == 'mercedes-benz') & (df['model_name'] == 'g-class') & (df['front_legroom (in)'] > 50), 'front_legroom (in)'] = 38.7
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'fuel_type'] = 'electric'
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'num_of_cylinders'] = 0.0
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'city_fuel_economy'] = 124.0
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'highway_fuel_economy'] = 102.00000
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'fuel_tank_volume (gallon)'] = np.nan
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'horsepower'] = np.nan
            df.loc[(df['make_name'] == 'bmw') & (df['model_name'] == 'i3'), 'torque (rpm)'] = np.nan
            
            # Combine correlated features
            df['volume'] = df['length (in)'] * df['width (in)'] * df['height (in)']
            df['combined_fuel_economy'] = df['city_fuel_economy'] + df['highway_fuel_economy']
            
            # Bucketize mileage and seller_rating
            df['mileage'] = pd.cut(df['mileage'], bins=[0, 50000, 100000, 150000, 200000, 650000], include_lowest=True,\
                                            labels=['0-50k', '50-100k', '100-150k', '150-200k', '>200k'])
            df['mileage'] = df['mileage'].cat.add_categories('unknown') # Add unknown category in case of missing values
            df['mileage'].fillna('unknown', inplace=True)
            
            df['seller_rating'] = pd.cut(df['seller_rating'], bins=[0, 1, 2, 3, 4, 5], include_lowest=True,\
                                                labels=['1 star', '2 star', '3 star', '4 star', '5 star'])
            df['seller_rating'] = df['seller_rating'].cat.add_categories('unknown')
            df['seller_rating'].fillna('unknown', inplace=True)

            # Reducing cardinality of categorical features
            df['exterior_color_grouped'] = np.where(df['exterior_color_grouped'].isin(\
                                                ['black', 'white', 'silver', 'gray', 'blue', 'red']),\
                                                df['exterior_color_grouped'], 'other')
            df['interior_color_grouped'] = np.where(df['interior_color_grouped'].isin(\
                                                ['black', 'gray', 'white', 'brown']),\
                                                df['interior_color_grouped'], 'other')
            top_20_make = df['make_name'].value_counts(sort=True).index[:20].tolist()
            df['make_name'] = np.where(df['make_name'].isin(top_20_make), df['make_name'], 'other')
            
            
            # Convert Dealer zip code to dealer region
            df['dealer_zip'] = df['dealer_zip'].astype(str)
            df['dealer_zip'] = df['dealer_zip'].str.strip().str.replace('.0', '', regex=False)
            search = SearchEngine()

            def get_state(zip_code):
                try:
                    zipcode = search.by_zipcode(zip_code)
                    return zipcode.state
                except:
                    return 'unknown'
                
            df['dealer_state'] = df['dealer_zip'].apply(get_state)
            region_dict = {'CA': 'West', 'TX': 'South', 'FL': 'South', 'NY': 'Northeast',
               'PA': 'Northeast', 'IL': 'Midwest', 'OH': 'Midwest', 'GA': 'South', 'NC': 'South',
               'MI': 'Midwest', 'NJ': 'Northeast', 'VA': 'South', 'WA': 'West', 'AZ': 'West',
               'MA': 'Northeast', 'TN': 'South', 'IN': 'Midwest', 'MO': 'Midwest', 'MD': 'South',
               'CO': 'West', 'MN': 'Midwest', 'SC': 'South', 'AL': 'South', 'LA': 'South', 'WI': 'Midwest',
               'OR': 'West', 'KY': 'South', 'OK': 'South', 'CT': 'Northeast', 'IA': 'Midwest', 'NV': 'West',
               'UT': 'West', 'AR': 'South', 'MS': 'South', 'KS': 'Midwest', 'NM': 'West', 'NE': 'Midwest',
               'NH': 'Northeast', 'ID': 'West', 'ME': 'Northeast', 'RI': 'Northeast', 'WV': 'South', 'MT': 'West',
               'DE': 'South', 'AK': 'West', 'DC': 'South', 'ND': 'Midwest', 'SD': 'Midwest', 'VT': 'Northeast',
               'WY': 'West', 'HI': 'West', 'PR': 'South', 'GU': 'West', 'VI': 'South', 'MP': 'West', 'AS': 'South',
               'FM': 'West', 'MH': 'West', 'PW': 'West', 'AA': 'South', 'AE': 'South', 'AP': 'South', 'unknown': 'unknown'}
            
            df['dealer_region'] = df['dealer_state'].map(region_dict)
            
            # Drop unnecessary columns
            cols_to_drop = ['daysonmarket', 'dealer_zip', 'major_options_count', 'dealer_state',\
                            'length (in)', 'width (in)', 'height (in)', 'city_fuel_economy', 'highway_fuel_economy', 'vin']
            df.drop(cols_to_drop, axis=1, inplace=True)
            
            os.makedirs(os.path.dirname(self.ingestion_config.raw_data_path), exist_ok=True)
            
            df.to_csv(self.ingestion_config.raw_data_path, index=False, header=True)
            
            logging.info("Train test split initiated")
            X = df.drop('actual_price', axis=1)
            Y = df['actual_price']
            X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=0.2, random_state=42, stratify=df['year'])
            
            
            # Create train, test, and validation datadframes
            df_train = pd.concat([X_train, Y_train], axis=1)
            df_test = pd.concat([X_test, Y_test], axis=1)
            
            df_train.reset_index(drop=True, inplace=True)
            df_test.reset_index(drop=True, inplace=True)
            
            # Save the dataframes
            df_train.to_csv(self.ingestion_config.train_data_path, index=False, header=True)
            df_test.to_csv(self.ingestion_config.test_data_path, index=False, header=True)
            logging.info("Train test split completed")
            
            logging.info("Data ingestion completed")
            
            return (
                self.ingestion_config.train_data_path,
                self.ingestion_config.test_data_path,
            )
        except Exception as e:
            logging.error("Error while ingesting data")
            raise CustomException(e, sys)
    