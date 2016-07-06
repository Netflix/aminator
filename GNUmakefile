validate:
	@rm -rf flake8; \
	virtualenv --no-site-packages flake8; \
	flake8/bin/pip install flake8; \
	export PATH=$$(pwd)/flake8/bin:$$PATH; \
	flake8 -v aminator
