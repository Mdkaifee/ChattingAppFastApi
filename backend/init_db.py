from database import Base, engine
import models

Base.metadata.create_all(bind=engine)

print("✅ All tables created successfully!")
