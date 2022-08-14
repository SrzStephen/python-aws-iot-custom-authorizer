deploy-dev:
	sam build -t template.yaml
	sam validate
	sam deploy --config-file samconfig-dev.toml --stack-name authorizer

deploy-prod:
	sam build -t template.yaml
	sam deploy --config-file samconfig-prod.toml --stack-name authorizer

install_all_deps:
	pip install src/authorizer/requirements.txt
	pip install tests/requirements.txt
