from ultralytics import RTDETR

model = RTDETR("/home/ubuntu/project/AI-HUB환경/sonography/rtdetr-l.pt")

model.train(
    data="/home/ubuntu/project/AI-HUB_preprocess/data.yaml",
    epochs=100,
    imgsz=640,
    batch=8,
    device=0,
    project="/home/ubuntu/project/AI-HUB_preprocess/runs",
    name = "rtdetr_aihub",
    patience=10,
    amp=False,
    lr0=0.0001,
    lrf=0.01,
    warmup_epochs=3,
    save=True,
    save_period=25,
    workers=4,
    fliplr=0.5,
    degrees=10.0,
    mosaic=0.0,      
    rect=False ,     
)