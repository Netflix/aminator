validate:
	@rm -rf pylint; \
	virtualenv-2.7 --no-site-packages pylint; \
	pylint/bin/pip install pylint boto bunch decorator envoy logutils pyyaml requests stevedore simplejson setuptools==5.3; \
	export PATH=$$(pwd)/pylint/bin:$$PATH; \
	which python; \
	python --version; \
	python -c "import setuptools; print 'setuptools: {}'.format(setuptools.__version__)"; \
	which pylint; \
	pylint --version; \
	pylint ./aminator
