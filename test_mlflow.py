import mlflow

mlflow.set_experiment("hotel-booking-v2")

with mlflow.start_run(run_name="test_run"):
    mlflow.log_param("test", "hello")
    mlflow.log_metric("score", 1.0)
    print("✅ MLflow test logged!")