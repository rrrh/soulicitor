.PHONY: install run clean

install:
	pip install fastapi uvicorn python-multipart pydantic

run:
	uvicorn main:app --reload

clean:
	rm -f vinyl.db
	find . -type d -name "__pycache__" -exec rm -rf {} +
