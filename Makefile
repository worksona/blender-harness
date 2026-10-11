BL   := scripts/bl
PORT ?= 8000

.PHONY: help setup doctor new world worlds serve docker-build docker-shell docker-claude clean

help:
	@echo "make setup               install headless Blender (idempotent)"
	@echo "make doctor              check Blender, Cycles, glTF export"
	@echo "make new NAME='Title'    scaffold worlds/<slug>/world.py"
	@echo "make world W=<slug>      build one world + top-down view (build/<slug>/top.jpg)"
	@echo "make worlds              build every world"
	@echo "make serve               web app on http://localhost:$(PORT)"
	@echo "make docker-build        build the Docker image"
	@echo "make docker-claude       run Claude Code inside the container"

setup:
	scripts/setup.sh

doctor:
	$(BL) tools/doctor.py

new:
	python3 tools/new_world.py "$(NAME)"

world:
	$(BL) tools/build_world.py $(W) --top

worlds:
	$(BL) tools/build_world.py --all

serve:
	python3 -m http.server $(PORT) -d app

docker-build:
	docker compose build

docker-shell:
	docker compose run --rm --service-ports harness

docker-claude:
	docker compose run --rm --service-ports harness claude

clean:
	rm -rf build
