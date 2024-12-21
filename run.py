from app import create_app

app = create_app()

with app.app_context():
    try:
        app.run(host="0.0.0.0")
    except KeyboardInterrupt:
        print("Stopped")
    except Exception as e:
        print(e)
