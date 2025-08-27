library identifier: 'JenkinsPythonHelperLibrary@2024.2.0', retriever: modernSCM(
  [$class: 'GitSCMSource',
   remote: 'https://github.com/UIUCLibrary/JenkinsPythonHelperLibrary.git',
   ])

def get_sonarqube_unresolved_issues(report_task_file){
    script{

        def props = readProperties  file: report_task_file
        def response = httpRequest url : props['serverUrl'] + '/api/issues/search?componentKeys=' + props['projectKey'] + '&resolved=no'
        def outstandingIssues = readJSON text: response.content
        return outstandingIssues
    }
}

def createWindowUVConfig(){
    def scriptFile = "ci\\jenkins\\scripts\\new-uv-global-config.ps1"
    if(! fileExists(scriptFile)){
        checkout scm
    }
    return powershell(
        label: 'Setting up uv.toml config file',
        script: "& ${scriptFile} \$env:UV_INDEX_URL \$env:UV_EXTRA_INDEX_URL",
        returnStdout: true
    ).trim()
}

def createUnixUvConfig(){

    def scriptFile = 'ci/jenkins/scripts/create_uv_config.sh'
    if(! fileExists(scriptFile)){
        checkout scm
    }
    return sh(label: 'Setting up uv.toml config file', script: "sh ${scriptFile} " + '$UV_INDEX_URL $UV_EXTRA_INDEX_URL', returnStdout: true).trim()
}


pipeline {
    agent none
    options {
        timeout(time: 1, unit: 'DAYS')
    }
    parameters{
        booleanParam(name: 'RUN_CHECKS', defaultValue: true, description: 'Run checks on code')
        booleanParam(name: 'TEST_RUN_TOX', defaultValue: false, description: 'Run Tox Tests')
        booleanParam(name: 'USE_SONARQUBE', defaultValue: true, description: 'Send data test data to SonarQube')
        credentials(name: 'SONARCLOUD_TOKEN', credentialType: 'org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl', defaultValue: 'sonarcloud_token', required: false)
    }
    stages{
        stage('Building and Testing'){
            stages{
                stage('Code Quality'){
                    stages{
                        stage('Building and Testing') {
                            agent {
                                docker{
                                    image 'python'
                                    label 'docker && linux'
                                    args '--mount source=python-tmp-uiucprescon_build,target=/tmp'
                                }
                            }
                            environment{
                                PIP_CACHE_DIR='/tmp/pipcache'
                                UV_TOOL_DIR='/tmp/uvtools'
                                UV_PYTHON_INSTALL_DIR='/tmp/uvpython'
                                UV_CACHE_DIR='/tmp/uvcache'
                                UV_CONFIG_FILE=createUnixUvConfig()
                            }
                            stages{
                                stage('Setting Up Building and Testing Environment'){
                                    options {
                                        retry(3)
                                    }
                                    steps{
                                        mineRepository()
                                        sh(
                                            label: 'Create virtual environment',
                                            script: '''python3 -m venv --clear bootstrap_uv
                                                       trap "rm -rf bootstrap_uv" EXIT
                                                       bootstrap_uv/bin/pip install --disable-pip-version-check uv
                                                       bootstrap_uv/bin/uv venv  --python-preference=only-system  venv
                                                       . ./venv/bin/activate
                                                       bootstrap_uv/bin/uv sync --locked --group dev --active
                                                       bootstrap_uv/bin/uv pip install uv --python venv
                                                       rm -rf bootstrap_uv
                                                       uv pip list
                                                       '''
                                                   )
                                        sh '''mkdir -p reports
                                              mkdir -p logs
                                           '''
                                    }
                                    post{
                                        failure{
                                            cleanWs(
                                                notFailBuild: true,
                                                deleteDirs: true,
                                                patterns: [
                                                    [pattern: 'logs/', type: 'INCLUDE'],
                                                    [pattern: 'reports/', type: 'INCLUDE'],
                                                    [pattern: 'venv/', type: 'INCLUDE'],
                                                ]
                                            )
                                        }
                                    }
                                }
                                stage('Building Docs'){
                                    steps{
                                        sh '''. ./venv/bin/activate
                                              sphinx-build docs build/docs/html -b html -d build/docs/.doctrees -v -w logs/build_sphinx_html.log -W --keep-going
                                           '''
                                    }
                                    post{
                                        always{
                                            recordIssues(tools: [sphinxBuild(pattern: 'logs/build_sphinx_html.log')])
                                        }
                                        success{
                                            publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'build/docs/html', reportFiles: 'index.html', reportName: 'Documentation', reportTitles: ''])
                                        }
                                    }
                                }
                                stage('Code Quality') {
                                    when{
                                        equals expected: true, actual: params.RUN_CHECKS
                                        beforeAgent true
                                    }
                                    stages{
                                        stage('Run Checks'){
                                            parallel{
                                                stage('Bandit'){
                                                    steps{
                                                        catchError(buildResult: 'SUCCESS', message: 'Bandit found some issues', stageResult: 'UNSTABLE') {
                                                            sh(
                                                                label: 'Run pydocstyle',
                                                                script: '''. ./venv/bin/activate
                                                                           mkdir -p reports/bandit
                                                                           bandit -c pyproject.toml --recursive src -f html -o reports/bandit/report.html
                                                                        '''
                                                            )
                                                        }
                                                    }
                                                    post {
                                                        unstable {
                                                            publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'reports/bandit', reportFiles: 'report.html', reportName: 'Bandit Report', reportTitles: ''])
                                                        }
                                                    }
                                                }
                                                stage('pyDocStyle'){
                                                    steps{
                                                        catchError(buildResult: 'SUCCESS', message: 'Did not pass all pyDocStyle tests', stageResult: 'UNSTABLE') {
                                                            sh(
                                                                label: 'Run pydocstyle',
                                                                script: '''. ./venv/bin/activate
                                                                           pydocstyle src > reports/pydocstyle-report.txt
                                                                        '''
                                                            )
                                                        }
                                                    }
                                                    post {
                                                        always{
                                                            recordIssues(tools: [pyDocStyle(pattern: 'reports/pydocstyle-report.txt')])
                                                        }
                                                    }
                                                }
                                                stage('PyTest'){
                                                    environment{
                                                        USERNAME='jenkins'
                                                    }
                                                    steps{
                                                        catchError(buildResult: 'UNSTABLE', message: 'Did not pass all pytest tests', stageResult: 'UNSTABLE') {
                                                            sh(
                                                                label: 'Running Pytest',
                                                                script:'''. ./venv/bin/activate
                                                                          coverage run --parallel-mode --source=src -m pytest --junitxml=reports/pytest.xml
                                                                          '''
                                                           )
                                                       }
                                                    }
                                                    post {
                                                        always {
                                                            junit 'reports/pytest.xml'
                                                        }
                                                        failure{
                                                            sh('pip list')
                                                        }
                                                    }
                                                }
                                                stage('Pylint'){
                                                    steps{
                                                        withEnv(['PYLINTHOME=/tmp/.cache/pylint']) {
                                                            catchError(buildResult: 'SUCCESS', message: 'Pylint found issues', stageResult: 'UNSTABLE') {
                                                                sh(label: 'Running pylint',
                                                                    script: '''. ./venv/bin/activate
                                                                               pylint src -r n --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" > reports/pylint.txt
                                                                            '''
                                                                )
                                                            }
                                                        }
                                                    }
                                                    post{
                                                        always{
                                                            recordIssues(tools: [pyLint(pattern: 'reports/pylint.txt')], name: 'PyLint', id: 'PyLint')
                                                            stash includes: 'reports/pylint_issues.txt,reports/pylint.txt', name: 'PYLINT_REPORT'
                                                        }
                                                    }
                                                }
                                                stage('Ruff') {
                                                    steps{
                                                        catchError(buildResult: 'SUCCESS', message: 'Ruff found issues', stageResult: 'UNSTABLE') {
                                                            sh(
                                                             label: 'Running Ruff',
                                                             script: '''. ./venv/bin/activate
                                                                        ruff check --config=pyproject.toml -o reports/ruffoutput.txt --output-format pylint --exit-zero
                                                                        ruff check --config=pyproject.toml -o reports/ruffoutput.json --output-format json
                                                                    '''
                                                             )
                                                        }
                                                    }
                                                    post{
                                                        always{
                                                            recordIssues(tools: [pyLint(pattern: 'reports/ruffoutput.txt', name: 'Ruff', id: 'Ruff')])
                                                        }
                                                    }
                                                }
                                                stage('Flake8') {
                                                    steps{
                                                        catchError(buildResult: 'SUCCESS', message: 'flake8 found some warnings', stageResult: 'UNSTABLE') {
                                                            sh(label: 'Running flake8',
                                                               script: '''. ./venv/bin/activate
                                                                          flake8 src --tee --output-file=logs/flake8.log
                                                                       '''
                                                            )
                                                        }
                                                    }
                                                    post {
                                                        always {
                                                            stash includes: 'logs/flake8.log', name: 'FLAKE8_REPORT'
                                                            recordIssues(tools: [flake8(name: 'Flake8', pattern: 'logs/flake8.log')])
                                                        }
                                                    }
                                                }
                                                stage('MyPy') {
                                                    steps{
                                                        catchError(buildResult: 'SUCCESS', message: 'MyPy found issues', stageResult: 'UNSTABLE') {
                                                            sh(
                                                                label: 'Running Mypy',
                                                                script: '''. ./venv/bin/activate
                                                                           mypy -p uiucprescon --html-report reports/mypy/html > logs/mypy.log
                                                                           '''
                                                           )
                                                        }
                                                    }
                                                    post {
                                                        always {
                                                            recordIssues(tools: [myPy(name: 'MyPy', pattern: 'logs/mypy.log')])
                                                            publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'reports/mypy/html/', reportFiles: 'index.html', reportName: 'MyPy HTML Report', reportTitles: ''])
                                                        }
                                                    }
                                                }
                                            }
                                            post{
                                                always{
                                                    sh(label: 'combining coverage data',
                                                       script: '''. ./venv/bin/activate
                                                                  coverage combine
                                                                  coverage xml -o ./reports/coverage-python.xml
                                                                  '''
                                                    )
                                                    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/coverage-python.xml'
                                                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'reports/coverage-python.xml']])
                                                }
                                            }
                                        }
                                        stage('Submit results to SonarQube'){
                                            options{
                                                lock('uiucpreson-sonarscanner')
                                            }
                                            environment{
                                                VERSION="${readTOML( file: 'pyproject.toml')['project'].version}"
                                            }
                                            when{
                                                allOf{
                                                    equals expected: true, actual: params.USE_SONARQUBE
                                                    expression{
                                                        try{
                                                            withCredentials([string(credentialsId: params.SONARCLOUD_TOKEN, variable: 'dddd')]) {
                                                                echo 'Found credentials for sonarqube'
                                                            }
                                                        } catch(e){
                                                            return false
                                                        }
                                                        return true
                                                    }
                                                }
                                            }
                                            steps{
                                                milestone ordinal: 1, label: 'sonarcloud'
                                                withSonarQubeEnv(installationName: 'sonarcloud', credentialsId: params.SONARCLOUD_TOKEN) {
                                                    sh(
                                                        label: 'Running Sonar Scanner',
                                                        script: "./venv/bin/uvx pysonar-scanner -Dsonar.projectVersion=${env.VERSION} -Dsonar.python.xunit.reportPath=./reports/pytest.xml -Dsonar.python.pylint.reportPaths=reports/pylint.txt -Dsonar.python.ruff.reportPaths=./reports/ruffoutput.json -Dsonar.python.coverage.reportPaths=./reports/coverage-python.xml -Dsonar.python.mypy.reportPaths=./logs/mypy.log ${env.CHANGE_ID ? '-Dsonar.pullrequest.key=$CHANGE_ID -Dsonar.pullrequest.base=$BRANCH_NAME' : '-Dsonar.branch.name=$BRANCH_NAME' }",
                                                    )
                                                }
                                                script{
                                                    timeout(time: 1, unit: 'HOURS') {
                                                        def sonarqubeResult = waitForQualityGate(abortPipeline: false)
                                                        if (sonarqubeResult.status != 'OK') {
                                                           unstable "SonarQube quality gate: ${sonarqubeResult.status}"
                                                        }
                                                        if(env.BRANCH_IS_PRIMARY){
                                                           writeJSON(file: 'reports/sonar-report.json', json: get_sonarqube_unresolved_issues('.scannerwork/report-task.txt'))
                                                           recordIssues(tools: [sonarQube(pattern: 'reports/sonar-report.json')])
                                                       }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            post{
                                cleanup{
                                    cleanWs(
                                        deleteDirs: true,
                                        patterns: [
                                            [pattern: 'build/', type: 'INCLUDE'],
                                            [pattern: 'venv/', type: 'INCLUDE'],
                                            [pattern: 'reports/', type: 'INCLUDE'],
                                            [pattern: 'logs/', type: 'INCLUDE'],
                                        ]
                                    )
                                }
                            }
                        }
                    }
                }
                stage('Tox') {
                    when{
                        equals expected: true, actual: params.TEST_RUN_TOX
                    }
                    parallel{
                        stage('Linux'){
                            when{
                                expression {return nodesByLabel('linux && docker && x86').size() > 0}
                            }
                            environment{
                                PIP_CACHE_DIR='/tmp/pipcache'
                                UV_TOOL_DIR='/tmp/uvtools'
                                UV_PYTHON_INSTALL_DIR='/tmp/uvpython'
                                UV_CACHE_DIR='/tmp/uvcache'
                            }
                            steps{
                                script{
                                    def envs = []
                                    node('docker && linux'){
                                        try{
                                            checkout scm
                                            withEnv(["UV_CONFIG_FILE=${createUnixUvConfig()}"]){
                                                docker.image('python').inside('--mount source=python-tmp-uiucprescon_build,target=/tmp'){
                                                    sh(script: 'python3 -m venv venv --clear && venv/bin/pip install --disable-pip-version-check uv')
                                                    envs = sh(
                                                        label: 'Get tox environments',
                                                        script: './venv/bin/uvx --quiet --with tox-uv tox list -d --no-desc',
                                                        returnStdout: true,
                                                    ).trim().split('\n')
                                                }
                                            }
                                        } finally{
                                            sh "${tool(name: 'Default', type: 'git')} clean -dfx"
                                        }
                                    }
                                    parallel(
                                        envs.collectEntries{toxEnv ->
                                            def version = toxEnv.replaceAll(/py(\d)(\d+).*/, '$1.$2')
                                            [
                                                "Tox Environment: ${toxEnv}",
                                                {
                                                    node('docker && linux'){
                                                        checkout scm
                                                        def image = docker.build(UUID.randomUUID().toString(), '-f ci/docker/linux/tox/Dockerfile --build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL --build-arg PIP_DOWNLOAD_CACHE=/.cache/pip --build-arg UV_CACHE_DIR .')
                                                        try{
                                                            withEnv([
                                                                'PIP_CACHE_DIR=/tmp/pipcache',
                                                                'UV_TOOL_DIR=/tmp/uvtools',
                                                                'UV_PYTHON_INSTALL_DIR=/tmp/uvpython',
                                                                'UV_CACHE_DIR=/tmp/uvcache',
                                                                "UV_CONFIG_FILE=${createUnixUvConfig()}",

                                                            ]){
                                                                try{
                                                                    image.inside('--mount source=python-tmp-uiucprescon_build,target=/tmp'){
                                                                        retry(3){
                                                                            try{
                                                                                sh( label: 'Running Tox',
                                                                                    script: """python3 -m venv venv --clear
                                                                                                ./venv/bin/pip install --disable-pip-version-check uv
                                                                                               ./venv/bin/uvx -p ${version} --python-preference only-system --with tox-uv tox run -e ${toxEnv} --runner uv-venv-lock-runner -vvv
                                                                                            """
                                                                                    )
                                                                            } catch(e) {
                                                                                cleanWs(
                                                                                    notFailBuild: true,
                                                                                    deleteDirs: true,
                                                                                    patterns: [
                                                                                        [pattern: '.tox/', type: 'INCLUDE'],
                                                                                        [pattern: 'venv/', type: 'INCLUDE'],
                                                                                    ]
                                                                                )
                                                                                throw e
                                                                            }
                                                                        }
                                                                    }
                                                                } finally{
                                                                    sh "${tool(name: 'Default', type: 'git')} clean -dfx"
                                                                }
                                                            }
                                                        } finally {
                                                            sh "docker rmi --no-prune ${image.id}"
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    )
                                }
                            }
                        }
                        stage('Windows') {
                            when{
                                expression {return nodesByLabel('windows && docker && x86').size() > 0}
                            }
                            environment{
                                 PIP_CACHE_DIR='C:\\Users\\ContainerUser\\Documents\\pipcache'
                                 UV_TOOL_DIR='C:\\Users\\ContainerUser\\Documents\\uvtools'
                                 UV_PYTHON_INSTALL_DIR='C:\\Users\\ContainerUser\\Documents\\uvpython'
                                 UV_CACHE_DIR='C:\\Users\\ContainerUser\\Documents\\uvcache'
//                                 VC_RUNTIME_INSTALLER_LOCATION='c:\\msvc_runtime\\'
                            }
                            steps{
                                script{
                                    def envs = []
                                    node('docker && windows'){
                                        checkout scm
                                        try{
                                            withEnv(["UV_CONFIG_FILE=${createWindowUVConfig()}"]){
                                                docker.image(env.DEFAULT_PYTHON_DOCKER_IMAGE ? env.DEFAULT_PYTHON_DOCKER_IMAGE: 'python')
                                                    .inside("\
                                                        --mount type=volume,source=uv_python_install_dir,target=${env.UV_PYTHON_INSTALL_DIR} \
                                                        --mount type=volume,source=pipcache,target=${env.PIP_CACHE_DIR} \
                                                        --mount type=volume,source=uv_cache_dir,target=${env.UV_CACHE_DIR}\
                                                        "
                                                    ){
                                                    bat(script: 'python -m venv venv --clear && venv\\Scripts\\pip install --disable-pip-version-check uv')
                                                    envs = bat(
                                                        label: 'Get tox environments',
                                                        script: '@.\\venv\\Scripts\\uvx --quiet --with tox-uv tox list -d --no-desc',
                                                        returnStdout: true,
                                                    ).trim().split('\r\n')
                                                }
                                            }
                                        } finally{
                                            bat "${tool(name: 'Default', type: 'git')} clean -dfx"
                                        }
                                    }
                                    parallel(
                                        envs.collectEntries{toxEnv ->
                                            def version = toxEnv.replaceAll(/py(\d)(\d+).*/, '$1.$2')
                                            [
                                                "Tox Environment: ${toxEnv}",
                                                {
                                                    node('docker && windows'){
                                                        retry(1){
                                                            checkout scm
                                                            def image
                                                            lock("${env.JOB_NAME} - ${env.NODE_NAME}"){
                                                                image = docker.build(UUID.randomUUID().toString(), '-f ci/docker/windows/Dockerfile --build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL --build-arg CHOCOLATEY_SOURCE --build-arg chocolateyVersion' + (env.DEFAULT_DOCKER_DOTNET_SDK_BASE_IMAGE ? " --build-arg FROM_IMAGE=${env.DEFAULT_DOCKER_DOTNET_SDK_BASE_IMAGE} ": ' ') + '.')
                                                            }
                                                            try{
                                                                try{
                                                                    withEnv(["UV_CONFIG_FILE=${createWindowUVConfig()}"]){
                                                                        image.inside("\
                                                                             --mount type=volume,source=uv_python_install_dir,target=${env.UV_PYTHON_INSTALL_DIR} \
                                                                             --mount type=volume,source=pipcache,target=${env.PIP_CACHE_DIR} \
                                                                             --mount type=volume,source=uv_cache_dir,target=${env.UV_CACHE_DIR}\
                                                                             "
                                                                         ){
                                                                            retry(3){
                                                                                try{
                                                                                    powershell(label: 'Running Tox',
                                                                                        script: """uv python install cpython-${version}
                                                                                                   uvx -p ${version} --with tox-uv tox run -e ${toxEnv} --runner uv-venv-lock-runner -vv
                                                                                            """
                                                                                    )
                                                                                } catch(e) {
                                                                                    cleanWs(
                                                                                        notFailBuild: true,
                                                                                        deleteDirs: true,
                                                                                        patterns: [
                                                                                            [pattern: '.tox/', type: 'INCLUDE'],
                                                                                            [pattern: 'venv/', type: 'INCLUDE'],
                                                                                        ]
                                                                                    )
                                                                                    throw e
                                                                                }
                                                                            }
                                                                        }
                                                                    }
                                                                } finally {
                                                                    bat "${tool(name: 'Default', type: 'git')} clean -dfx"
                                                                }
                                                            } finally{
                                                                bat "docker rmi --no-prune ${image.id}"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    )
                                }
                            }
                        }
                        stage('MacOS'){
                            when{
                                expression {return nodesByLabel('mac && python3').size() > 0}
                            }
                            steps{
                                script{
                                    node('mac && python3'){
                                        try{
                                            checkout scm
                                            withEnv(["UV_CONFIG_FILE=${createUnixUvConfig()}"]){
                                                sh(script: 'python3 -m venv venv --clear && venv/bin/pip install --disable-pip-version-check uv')
                                                envs = sh(
                                                    label: 'Get tox environments',
                                                    script: './venv/bin/uvx --quiet --with tox-uv tox list -d --no-desc',
                                                    returnStdout: true,
                                                ).trim().split('\n')
                                            }
                                        } finally{
                                            sh "${tool(name: 'Default', type: 'git')} clean -dfx"
                                        }
                                    }
                                    parallel(
                                        envs.collectEntries{toxEnv ->
                                            def version = toxEnv.replaceAll(/py(\d)(\d+).*/, '$1.$2')
                                            [
                                                "Tox Environment: ${toxEnv}",
                                                {
                                                    node('mac && python3'){
                                                        checkout scm
                                                        withEnv(["UV_CONFIG_FILE=${createUnixUvConfig()}",]){
                                                            try{
                                                                retry(3){
                                                                    try{
                                                                        sh( label: 'Running Tox',
                                                                            script: """python3 -m venv venv --clear && ./venv/bin/pip install --disable-pip-version-check uv
                                                                                       ./venv/bin/uvx -p ${version} --python-preference only-system --with tox-uv tox run -e ${toxEnv} --runner uv-venv-lock-runner -vvv
                                                                                    """
                                                                        )
                                                                    } catch(e) {
                                                                        cleanWs(
                                                                            notFailBuild: true,
                                                                            deleteDirs: true,
                                                                            patterns: [
                                                                                [pattern: '.tox/', type: 'INCLUDE'],
                                                                                [pattern: 'venv/', type: 'INCLUDE'],
                                                                            ]
                                                                        )
                                                                        throw e
                                                                    }
                                                                }
                                                            } finally{
                                                                sh "${tool(name: 'Default', type: 'git')} clean -dfx"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
