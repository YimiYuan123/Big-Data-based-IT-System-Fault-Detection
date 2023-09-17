# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 20:20:00 2023

@author: LENOVO
"""
import os
# 查看当前工作目录  
retval = os.getcwd()
# 修改当前工作目录  
os.chdir('E:/')  
 
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

folder_path = "E:/labels"
csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

# create an empty list to store data frames
dfs = []

# read CSV files and store them as DataFrames in the list
for file in csv_files:
    path = os.path.join(folder_path, file)
    df = pd.read_csv(path)
    dfs.append(df)
    
# concatenate all data frames vertically
df = pd.concat(dfs, axis=0, ignore_index=True)
df=df.drop_duplicates(subset=['id'],keep='first').reset_index(drop=True)
df.to_csv("labelsTotal.csv")












