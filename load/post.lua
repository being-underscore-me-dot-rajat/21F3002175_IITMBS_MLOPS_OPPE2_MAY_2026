-- wrk POST body for /predict (Deliverable 6)
wrk.method  = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"age":58,"gender":"male","cp":2,"trestbps":140,"chol":211,"fbs":1,"restecg":0,"thalach":165,"exang":0,"oldpeak":0.0,"slope":2,"ca":0,"thal":2}'
