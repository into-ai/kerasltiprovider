"""
Tasks for maintaining the project.

Execute 'invoke --list' for guidance on using Invoke
"""
import shutil
from ruamel.yaml import YAML
import pprint

from invoke import task
import webbrowser
from pathlib import Path

Path().expanduser()
yaml = YAML()

ROOT_DIR = Path(__file__).parent
SETUP_FILE = ROOT_DIR.joinpath("setup.py")
TEST_DIR = ROOT_DIR.joinpath("tests")
SOURCE_DIR = ROOT_DIR.joinpath("kerasltiprovider")
TOX_DIR = ROOT_DIR.joinpath(".tox")
TRAVIS_CONFIG_FILE = ROOT_DIR.joinpath(".travis.yml")
COVERAGE_FILE = ROOT_DIR.joinpath(".coverage")
COVERAGE_DIR = ROOT_DIR.joinpath("htmlcov")
COVERAGE_REPORT = COVERAGE_DIR.joinpath("index.html")
DOCS_DIR = ROOT_DIR.joinpath("docs")
DOCS_BUILD_DIR = DOCS_DIR.joinpath("build")
DOCS_INDEX = DOCS_BUILD_DIR.joinpath("index.html")
PYTHON_DIRS = [str(d) for d in [SOURCE_DIR, TEST_DIR]]


def test_env_run(c, cmd):
    env = "FLASK_SECRET_KEY=123 CONSUMER_KEY_SECRET=123"
    c.run("{} {}".format(env, cmd))


def _delete_file(file):
    try:
        file.unlink(missing_ok=True)
    except TypeError:
        # missing_ok argument added in 3.8
        try:
            file.unlink()
        except FileNotFoundError:
            pass


@task(help={"check": "Checks if source is formatted without applying changes"})
def format(c, check=False):
    """Format code
    """
    python_dirs_string = " ".join(PYTHON_DIRS)
    black_options = "--diff" if check else ""
    test_env_run(c, "pipenv run black {} {}".format(black_options, python_dirs_string))
    isort_options = "--recursive {}".format("--check-only" if check else "")
    test_env_run(c, "pipenv run isort {} {}".format(isort_options, python_dirs_string))


@task
def lint(c):
    """Lint code
    """
    test_env_run(c, "pipenv run flake8 {}".format(SOURCE_DIR))


@task
def test(c, min_coverage=None):
    """Run tests
    """
    pytest_options = "--cov-fail-under={}".format(min_coverage) if min_coverage else ""
    test_env_run(c, "pipenv run pytest --cov={} {}".format(SOURCE_DIR, pytest_options))


@task
def type_check(c):
    """Check types
    """
    test_env_run(c, "pipenv run mypy")


def _create(d, *keys):
    current = d
    for key in keys:
        try:
            current = current[key]
        except (TypeError, KeyError):
            current[key] = dict()
            current = current[key]


def _fix_token(config_file=None, force=False, verify=True):
    config_file = config_file or TRAVIS_CONFIG_FILE
    with open(config_file, "r") as _file:
        try:
            travis_config = yaml.load(_file)
        except Exception:
            raise ValueError(
                "Failed to parse the travis configuration. "
                "Make sure the config only contains valid YAML and keys as specified by travis."
            )

        # Get the generated token from the top level deploy config added by the travis cli
        try:
            real_token = travis_config["deploy"]["password"]["secure"]
        except (TypeError, KeyError):
            raise AssertionError("Can't find any top level deployment tokens")

        try:
            # Find the build stage that deploys to PyPI
            pypy_stages = [
                stage
                for stage in travis_config["jobs"]["include"]
                if stage.get("deploy", dict()).get("provider") == "pypi"
            ]
            assert (
                len(pypy_stages) > 0
            ), "Can't set the new token because there are no stages deploying to PyPI"
            assert (
                len(pypy_stages) < 2
            ), "Can't set the new token because there are multiple stages deploying to PyPI"
        except (TypeError, KeyError):
            raise AssertionError("Can't set the new token because there no build stages")

        try:
            is_mock_token = pypy_stages[0]["deploy"]["password"]["secure"] == "REPLACE_ME"
            is_same_token = pypy_stages[0]["deploy"]["password"]["secure"] == real_token

            unmodified = is_mock_token or is_same_token
        except (TypeError, KeyError):
            unmodified = False

        # Set the new generated token as the stages deploy token
        _create(pypy_stages[0], "deploy", "password", "secure")
        pypy_stages[0]["deploy"]["password"]["secure"] = real_token

        # Make sure it is fine to overwrite the config file
        assert unmodified or force, (
            'The secure token in the "{}" stage has already been changed. '
            "Retry with --force if you are sure about replacing it.".format(
                pypy_stages[0].get("stage", "PyPI deployment")
            )
        )

        # Remove the top level deploy config added by the travis cli
        travis_config.pop("deploy")

        if not unmodified and verify:
            pprint.pprint(travis_config)
            if (
                not input("Do you want to save this configuration? (y/n) ")
                .strip()
                .lower()
                == "y"
            ):
                return

    # Save the new travis config
    assert travis_config
    with open(config_file, "w") as _file:
        yaml.dump(travis_config, _file)
    print("Fixed!")


@task(help=dict(
    force="Force overriding the current travis configuration",
    verify="Verify config changes by asking for the user's approval"
))
def fix_token(c, force=False, verify=True):
    """
    Add the token generated by the travis cli script to the correct entry
    """
    _fix_token(force=force, verify=verify)


@task
def install_hooks(c):
    """Install pre-commit hooks
    """
    test_env_run(c, "pipenv run pre-commit install -t pre-commit")
    test_env_run(c, "pipenv run pre-commit install -t pre-push")


@task
def pre_commit(c):
    """Run all pre-commit checks
    """
    test_env_run(c, "pipenv run pre-commit run --all-files")


@task(
    pre=[test],
    help=dict(
        publish="Publish the result (default False)",
        provider="The provider to publish (default codecov)",
    ),
)
def coverage(c, publish=False, provider="codecov"):
    """Create coverage report
    """
    if publish:
        # Publish the results via provider (e.g. codecov or coveralls)
        test_env_run(c, "pipenv run {}".format(provider))
    else:
        # Build a local report
        test_env_run(c, "pipenv run coverage html -d {}".format(COVERAGE_DIR))
        webbrowser.open(COVERAGE_REPORT.as_uri())


@task(help={"output": "Generated documentation output format (default is html)"})
def docs(c, output="html"):
    """Generate documentation
    """
    test_env_run(c,
        "pipenv run sphinx-apidoc -o {} kerasltiprovider".format(
            DOCS_DIR
        )
    )
    test_env_run(c,
        "pipenv run sphinx-build -b {} {} {}".format(
            output.lower(), DOCS_DIR, DOCS_BUILD_DIR
        )
    )
    if output.lower() == "html":
        webbrowser.open(DOCS_INDEX.as_uri())
    elif output.lower() == "latex":
        test_env_run(c, "cd {} && make".format(DOCS_BUILD_DIR))


@task
def clean_docs(c):
    """Clean up files from documentation builds
    """
    test_env_run(c, "rm -fr {}".format(DOCS_BUILD_DIR))


@task
def clean_build(c):
    """Clean up files from package building
    """
    test_env_run(c, "rm -fr build/")
    test_env_run(c, "rm -fr dist/")
    test_env_run(c, "rm -fr .eggs/")
    test_env_run(c, "find . -name '*.egg-info' -exec rm -fr {} +")
    test_env_run(c, "find . -name '*.egg' -exec rm -f {} +")


@task
def clean_python(c):
    """Clean up python file artifacts
    """
    test_env_run(c, "find . -name '*.pyc' -exec rm -f {} +")
    test_env_run(c, "find . -name '*.pyo' -exec rm -f {} +")
    test_env_run(c, "find . -name '*~' -exec rm -f {} +")
    test_env_run(c, "find . -name '__pycache__' -exec rm -fr {} +")


@task
def clean_tests(c):
    """Clean up files from testing
    """
    _delete_file(COVERAGE_FILE)
    shutil.rmtree(TOX_DIR, ignore_errors=True)
    shutil.rmtree(COVERAGE_DIR, ignore_errors=True)


@task(pre=[clean_build, clean_python, clean_tests, clean_docs])
def clean(c):
    """Runs all clean sub-tasks
    """
    pass


@task(clean)
def dist(c):
    """Build source and wheel packages
    """
    test_env_run(c, "python setup.py sdist")
    test_env_run(c, "python setup.py bdist_wheel")


@task(pre=[clean, dist])
def release(c):
    """Make a release of the python package to pypi
    """
    test_env_run(c, "twine upload dist/*")
