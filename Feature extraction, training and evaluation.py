import os
# 查看当前工作目录  
retval = os.getcwd()
# 修改当前工作目录  
os.chdir('E:/')  
 
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from tqdm.auto import tqdm
from xgboost import XGBClassifier



def read_feature():
    all_ids = set([i.split("_")[0] for i in os.listdir("./inputs/metric/")]) |\
            set([i.split("_")[0] for i in os.listdir("./inputs/log/")]) |\
            set([i.split("_")[0] for i in os.listdir("./inputs/trace/")])
    all_ids = list(all_ids)
    print("IDs Length =", len(all_ids))
    feature = pd.DataFrame(Parallel(n_jobs=6, backend="multiprocessing")(delayed(processing_feature)(f) for f in tqdm(all_ids))) # change njobs to -1, utlize all CPU cores
    return feature

def sScore(y_true, y_pred):
    score = []
    for i in range(num_classes):
        score.append(roc_auc_score(y_true[:, i], y_pred[:, i]))
        
    return score

def processing_feature(file):
    log, trace, metric, metric_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if os.path.exists(f"./inputs/log/{file}_log.csv"):
        log = pd.read_csv(f"./inputs/log/{file}_log.csv").sort_values(by=['timestamp']).reset_index(drop=True)
    
    if os.path.exists(f"./inputs/trace/{file}_trace.csv"):
        trace = pd.read_csv(f"./inputs/trace/{file}_trace.csv").sort_values(by=['timestamp']).reset_index(drop=True)
        
    if os.path.exists(f"./inputs/metric/{file}_metric.csv"):
        metric = pd.read_csv(f"./inputs/metric/{file}_metric.csv").sort_values(by=['timestamp']).reset_index(drop=True)
    
    feats = {"id" : file}
    if len(trace) > 0:
        feats['trace_length'] = len(trace)
        feats[f"trace_status_code_std"] = trace['status_code'].apply("std")
        
        for stats_func in ['mean', 'std', 'skew', 'nunique']:
            feats[f"trace_timestamp_{stats_func}"] = trace['timestamp'].apply(stats_func)
            
        for stats_func in ['nunique']:
            for i in ['host_ip', 'service_name', 'endpoint_name', 'trace_id', 'span_id', 'parent_id', 'start_time', 'end_time']:
                feats[f"trace_{i}_{stats_func}"] = trace[i].agg(stats_func)
                
    else:
        feats['trace_length'] = -1
                
    if len(log) > 0:
        feats['log_length'] = len(log)
        log['message_length'] = log['message'].fillna("").map(len)
        log['log_info_length'] = log['message'].map(lambda x:x.split("INFO")).map(len)
        
    else:
        feats['log_length'] = -1

    if len(metric) > 0:
        feats['metric_length'] = len(metric)
        feats['metric_value_timestamp_value_mean_std'] = metric.groupby(['timestamp'])['value'].mean().std()
        
    else:
        feats['metric_length'] = -1

    return feats

def gen_label(train):
    col = np.zeros((train.shape[0], 9))
    for i, label in enumerate(train['label'].values):
        col[i][label] = 1
        
    return col

# global variables
num_classes = 9
n_splits = 5



feature = pd.read_csv("E:/feature.csv")

label = pd.read_csv("E:/labelsTotal.csv")
lb_encoder = LabelEncoder()
label['label'] = lb_encoder.fit_transform(label['source'])

all_data = feature.merge(label[['id', 'label']].groupby(['id'], as_index=False)['label'].agg(list), how='left', on=['id']).set_index("id")
not_use = ['id', 'label']
feature_name = [i for i in all_data.columns if i not in not_use]
X = all_data[feature_name].replace([np.inf, -np.inf], 0).clip(-1e9, 1e9)
print(f"Feature Length = {len(feature_name)}")
print(f"Feature = {feature_name}")


kf = MultilabelStratifiedKFold(n_splits=n_splits, random_state=3407, shuffle=True)
scaler = StandardScaler()
scaler_X = scaler.fit_transform(X.fillna(0).replace([np.inf, -np.inf], 0))

y = gen_label(all_data[all_data['label'].notnull()])
train_scaler_X = scaler_X[all_data['label'].notnull()]
test_scaler_X = scaler_X[all_data['label'].isnull()]

ovr_oof = np.zeros((len(train_scaler_X), num_classes))
ovr_preds = np.zeros((len(test_scaler_X), num_classes))

for train_index, valid_index in kf.split(train_scaler_X, y):
    X_train, X_valid = train_scaler_X[train_index], train_scaler_X[valid_index]
    y_train, y_valid = y[train_index], y[valid_index]
    clf = OneVsRestClassifier(XGBClassifier(random_state=0, n_jobs=-1)) # change njobs to -1, utlize all CPU cores
    clf.fit(X_train, y_train)
    ovr_oof[valid_index] = clf.predict_proba(X_valid)
    ovr_preds = clf.predict_proba(test_scaler_X) / n_splits
    score = sScore(y_valid, ovr_oof[valid_index])
    print(f"Score = {np.mean(score)}")

each_score = sScore(y, ovr_oof)
score_metric = pd.DataFrame(each_score, columns=['score'], index=list(lb_encoder.classes_))
score_metric.loc["Weighted AVG.", "score"] = np.mean(score_metric['score'])
print(score_metric)

# submit
submit = pd.DataFrame(ovr_preds, columns=lb_encoder.classes_)
submit.index = X[all_data['label'].isnull()].index
submit.reset_index(inplace=True)
submit = submit.melt(id_vars="id", value_vars=lb_encoder.classes_, value_name="score", var_name="source")
submit.to_csv("baseline2.csv", index=False)
