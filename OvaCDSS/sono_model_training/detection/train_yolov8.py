from ultralytics import YOLO

model = YOLO("/home/ubuntu/project/AI-HUB환경/sonography/yolov8n.pt")

model.train(
    data = "/home/ubuntu/project/AI-HUB_preprocess/data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    device=0,
    warmup_epochs = 3,
    project="/home/ubuntu/project/AI-HUB_preprocess/runs",
    name="yolov8n_aihub",
    patience=10, #Stop if there is no improvement for 10 epochs
    val=True,
    lr0 = 0.01,
    cos_lr=True,
    save=True,
    save_period = 25,
    workers = 4,
    fliplr = 0.5,
    degrees = 10.0,
    mosaic = 1.0,
    rect = False,
    amp=False,
    flipud=0.3,
    
)