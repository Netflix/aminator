validate:
	@rm -rf pylint; \
	virtualenv-2.7 pylint; \
	pylint/bin/pip install pylint==1.2.1 boto bunch decorator envoy logutils pyyaml requests stevedore simplejson setuptools; \
	export PATH=$$(pwd)/pylint/bin:$$PATH; \
	find aminator -name \*.py | while read py; do \
		lintfile=$$(dirname $$py)/.$$(basename $$py).pylint; \
		[ $$lintfile -nt $$py ] && echo "$$py OK" && continue; \
		pylint --persistent=no --rcfile=/dev/null --disable=C,global-statement,broad-except,star-args,abstract-class-not-used,too-many-instance-attributes,too-few-public-methods,fixme,import-error,R,I,attribute-defined-outside-init,unused-argument,protected-access,super-on-old-class --report=no $$py && echo "$$py OK" || exit 1; \
		touch $$lintfile; \
	 done
