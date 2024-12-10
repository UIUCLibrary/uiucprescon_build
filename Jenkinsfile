library identifier: 'JenkinsPythonHelperLibrary@2024.2.0', retriever: modernSCM(
  [$class: 'GitSCMSource',
   remote: 'https://github.com/UIUCLibrary/JenkinsPythonHelperLibrary.git',
   ])


def getMacToxTestsParallel(args = [:]){
    def nodeLabel = args['label']
    args.remove('label')

    def envNamePrefix = args['envNamePrefix']
    args.remove('envNamePrefix')

    def retries = args.get('retry', 1)
    if(args.containsKey('retry')){
        args.remove('retry')
    }
    if(args.size() > 0){
        error "getMacToxTestsParallel has invalid arguments ${args.keySet()}"
    }

    //    =============================================
    def envs = [:]
    node(nodeLabel){
        try{
            checkout scm
            sh(
                script: '''python3 -m venv venv --upgrade-deps
                    venv/bin/pip install tox
                    '''
            )
            def toxEnvs = sh(
                    label: 'Getting Tox Environments',
                    returnStdout: true,
                    script: 'venv/bin/tox list -d --no-desc'
                ).trim().split('\n')
            toxEnvs.each({env ->
                def requiredPythonVersion = sh(
                    label: "Getting required python version for Tox Environment: ${env}",
                    script: "venv/bin/tox config -e  ${env} -k py_dot_ver  | grep  'py_dot_ver =' | sed -E 's/py_dot_ver = ([0-9].[0-9]+)/\\1/g'",
                    returnStdout: true
                ).trim()
                envs[env] = requiredPythonVersion
            })


        } finally {
            sh 'rm -rf venv'
        }
    }
    echo "Found tox environments for ${envs.keySet().join(', ')}"
    def jobs = envs.collectEntries({ toxEnv, requiredPythonVersion ->
        def jenkinsStageName = "${envNamePrefix} ${toxEnv}"
        def jobNodeLabel = "${nodeLabel} && python${requiredPythonVersion}"
        if(nodesByLabel(jobNodeLabel).size() > 0){
            [jenkinsStageName,{
                retry(retries){
                    node(jobNodeLabel){
                        try{
                            checkout scm
                            sh(
                                script: '''python3 -m venv venv --upgrade-deps
                                    venv/bin/pip install tox
                                    '''
                            )
                            sh(
                                label: 'Getting Tox Environments',
                                script: "venv/bin/tox --list-dependencies --workdir=.tox run -e ${toxEnv}"
                                )

                        } finally {
                            cleanWs(
                                notFailBuild: true,
                                deleteDirs: true,
                                patterns: [
                                    [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                    [pattern: 'venv/', type: 'INCLUDE'],
                                    [pattern: '.tox/', type: 'INCLUDE'],
                                ]
                            )
                        }
                    }
                }

            }]
        } else {
            echo "Unable to add ${toxEnv} because no nodes with required labels: ${jobNodeLabel}"
        }
    })
    return jobs
}
pipeline {
    agent none
    options {
        timeout(time: 1, unit: 'DAYS')
    }
    parameters{
        booleanParam(name: 'TEST_RUN_TOX', defaultValue: false, description: 'Run Tox Tests')
    }
    stages{
        stage('Building and Testing'){
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
                        UV_INDEX_STRATEGY='unsafe-best-match'
                        UV_TOOL_DIR='/tmp/uvtools'
                        UV_PYTHON_INSTALL_DIR='/tmp/uvpython'
                        UV_CACHE_DIR='/tmp/uvcache'
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
                                               bootstrap_uv/bin/uv pip install uv -r requirements-ci.txt --python venv
                                               '''
                                           )
                                sh(
                                    label: 'Install package in development mode',
                                    script: '''. ./venv/bin/activate
                                               uv pip install -e .
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
                            stages{
                                stage('Run Checks'){
                                    parallel{
                                        stage('pyDocStyle'){
                                            steps{
                                                catchError(buildResult: 'SUCCESS', message: 'Did not pass all pyDocStyle tests', stageResult: 'UNSTABLE') {
                                                    sh(
                                                        label: 'Run pydocstyle',
                                                        script: '''. ./venv/bin/activate
                                                                   pydocstyle uiucprescon > reports/pydocstyle-report.txt
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
                                                                  coverage run --parallel-mode --source=uiucprescon -m pytest --junitxml=reports/pytest.xml
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
                                                                       pylint uiucprescon.build -r n --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" > reports/pylint.txt
                                                                    '''

                                                        )
                                                    }
                                                }
                                            }
                                            post{
                                                always{
                                                    recordIssues(tools: [pyLint(pattern: 'reports/pylint.txt')])
                                                    stash includes: 'reports/pylint_issues.txt,reports/pylint.txt', name: 'PYLINT_REPORT'
                                                }
                                            }
                                        }
                                        stage('Flake8') {
                                            steps{
                                                catchError(buildResult: 'SUCCESS', message: 'flake8 found some warnings', stageResult: 'UNSTABLE') {
                                                    sh(label: 'Running flake8',
                                                       script: '''. ./venv/bin/activate
                                                                  flake8 uiucprescon --tee --output-file=logs/flake8.log
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
                                UV_INDEX_STRATEGY='unsafe-best-match'
                                UV_TOOL_DIR='/tmp/uvtools'
                                UV_PYTHON_INSTALL_DIR='/tmp/uvpython'
                                UV_CACHE_DIR='/tmp/uvcache'
                            }
                            steps{
                                script{
                                    def envs = []
                                    node('docker && linux'){
                                        docker.image('python').inside('--mount source=python-tmp-uiucprescon_build,target=/tmp'){
                                            try{
                                                checkout scm
                                                sh(script: 'python3 -m venv venv --clear && venv/bin/pip install --disable-pip-version-check uv')
                                                envs = sh(
                                                    label: 'Get tox environments',
                                                    script: './venv/bin/uvx --quiet --with tox-uv tox list -d --no-desc',
                                                    returnStdout: true,
                                                ).trim().split('\n')
                                            } finally{
                                                cleanWs(
                                                    patterns: [
                                                        [pattern: 'venv/', type: 'INCLUDE'],
                                                        [pattern: '.tox', type: 'INCLUDE'],
                                                        [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                    ]
                                                )
                                            }
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
                                                                'UV_INDEX_STRATEGY=unsafe-best-match',
                                                                'UV_TOOL_DIR=/tmp/uvtools',
                                                                'UV_PYTHON_INSTALL_DIR=/tmp/uvpython',
                                                                'UV_CACHE_DIR=/tmp/uvcache',
                                                            ]){
                                                                try{
                                                                    image.inside('--mount source=python-tox-tmp-pykdu,target=/tmp'){
                                                                        try{
                                                                            sh( label: 'Running Tox',
                                                                                script: """python3 -m venv venv --clear && ./venv/bin/pip install --disable-pip-version-check uv
                                                                                           ./venv/bin/uvx -p ${version} --python-preference only-system --with tox-uv tox run -e ${toxEnv} -vvv
                                                                                        """
                                                                                )
                                                                        } catch(e) {
                                                                            if( fileExists('venv/bin/uv')){
                                                                                sh(script: '''. ./venv/bin/activate
                                                                                      uv python list
                                                                                      '''
                                                                                        )
                                                                            }
                                                                            throw e
                                                                        }
                                                                    }
                                                                } finally{
                                                                    cleanWs(
                                                                        patterns: [
                                                                            [pattern: 'venv/', type: 'INCLUDE'],
                                                                            [pattern: '.tox', type: 'INCLUDE'],
                                                                            [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                                        ]
                                                                    )
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
                                 UV_INDEX_STRATEGY='unsafe-best-match'
                                 PIP_CACHE_DIR='C:\\Users\\ContainerUser\\Documents\\pipcache'
                                 UV_TOOL_DIR='C:\\Users\\ContainerUser\\Documents\\uvtools'
                                 UV_PYTHON_INSTALL_DIR='C:\\Users\\ContainerUser\\Documents\\uvpython'
                                 UV_CACHE_DIR='C:\\Users\\ContainerUser\\Documents\\uvcache'
                                 VC_RUNTIME_INSTALLER_LOCATION='c:\\msvc_runtime\\'
                            }
                            steps{
                                script{
                                    def envs = []
                                    node('docker && windows'){
                                        docker.image('python').inside('--mount source=python-tmp-uiucprescon_build,target=C:\\Users\\ContainerUser\\Documents'){
                                            try{
                                                checkout scm
                                                bat(script: 'python -m venv venv --clear && venv\\Scripts\\pip install --disable-pip-version-check uv')
                                                envs = bat(
                                                    label: 'Get tox environments',
                                                    script: '@.\\venv\\Scripts\\uvx --quiet --with tox-uv tox list -d --no-desc',
                                                    returnStdout: true,
                                                ).trim().split('\r\n')
                                            } catch(e) {
                                                bat 'dir'
                                                if( fileExists('venv')){
                                                    bat 'dir venv'
                                                }
                                                if (fileExists('venv\\Scripts')){
                                                    bat 'dir venv\\Scripts'
                                                }
                                                throw e
                                            } finally{
                                                cleanWs(
                                                    patterns: [
                                                        [pattern: 'venv/', type: 'INCLUDE'],
                                                        [pattern: '.tox/', type: 'INCLUDE'],
                                                        [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                    ]
                                                )
                                            }
                                        }
                                    }
                                    parallel(
                                        envs.collectEntries{toxEnv ->
                                            def version = toxEnv.replaceAll(/py(\d)(\d+).*/, '$1.$2')
                                            [
                                                "Tox Environment: ${toxEnv}",
                                                {
                                                    node('docker && windows'){
                                                        checkout scm
                                                        def image
                                                        lock("${env.JOB_NAME} - ${env.NODE_NAME}"){
                                                            image = docker.build(UUID.randomUUID().toString(), '-f ci/docker/windows/tox/Dockerfile --build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL --build-arg CHOCOLATEY_SOURCE --build-arg chocolateyVersion .')
                                                        }
                                                        try{
                                                            image.inside('--mount source=python-tmp-tox-uiucprescon_build,target=C:\\Users\\ContainerUser\\Documents'){
                                                                retry(3){
                                                                    bat(label: 'Running Tox',
                                                                        script: """python -m venv venv --clear && venv\\Scripts\\pip --disable-pip-version-check install uv
                                                                                   venv\\Scripts\\uv python install cpython-${version}
                                                                                   venv\\Scripts\\uvx -p ${version} --with tox-uv tox run -e ${toxEnv} -vv
                                                                                   rmdir /s/q venv
                                                                                   rmdir /s/q .tox
                                                                            """
                                                                    )
                                                                }
                                                            }
                                                        } finally{
                                                            bat "docker rmi --no-prune ${image.id}"
                                                            cleanWs(
                                                                patterns: [
                                                                    [pattern: 'venv/', type: 'INCLUDE'],
                                                                    [pattern: '.tox', type: 'INCLUDE'],
                                                                    [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                                ]
                                                            )
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
                            environment{
                                UV_INDEX_STRATEGY='unsafe-best-match'
                            }
                            steps{
                                script{
                                    node('mac && python3'){
                                        try{
                                            checkout scm
                                            sh(script: 'python3 -m venv venv --clear && venv/bin/pip install --disable-pip-version-check uv')
                                            envs = sh(
                                                label: 'Get tox environments',
                                                script: './venv/bin/uvx --quiet --with tox-uv tox list -d --no-desc',
                                                returnStdout: true,
                                            ).trim().split('\n')
                                        } finally{
                                            cleanWs(
                                                patterns: [
                                                    [pattern: 'venv/', type: 'INCLUDE'],
                                                    [pattern: '.tox', type: 'INCLUDE'],
                                                    [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                ]
                                            )
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
                                                        withEnv([
                                                            'UV_INDEX_STRATEGY=unsafe-best-match',
                                                        ]){
                                                            try{
                                                                sh( label: 'Running Tox',
                                                                    script: """python3 -m venv venv && ./venv/bin/pip install --disable-pip-version-check uv
                                                                               ./venv/bin/uvx -p ${version} --python-preference only-system --with tox-uv tox run -e ${toxEnv} -vvv
                                                                            """
                                                                    )
                                                            } catch(e) {
                                                                sh(script: '''. ./venv/bin/activate
                                                                              uv python list
                                                                           '''
                                                                   )
                                                                throw e
                                                            } finally{
                                                                cleanWs(
                                                                    patterns: [
                                                                        [pattern: 'venv/', type: 'INCLUDE'],
                                                                        [pattern: '.tox', type: 'INCLUDE'],
                                                                        [pattern: '**/__pycache__/', type: 'INCLUDE'],
                                                                    ]
                                                                )
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
