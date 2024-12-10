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
                stage('Building') {
                    agent {
                        dockerfile {
                            filename 'ci/docker/linux/jenkins/Dockerfile'
                            label 'linux && docker'
                            additionalBuildArgs '--build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL'
                        }
                    }
                    stages{
                        stage('Building Docs'){
                            steps{
                                sh 'python3 -m sphinx -W --keep-going -b html docs build/docs/html -w logs/build_sphinx_html.log'
                            }
                            post{
                                always{
                                    recordIssues(tools: [sphinxBuild(pattern: 'logs/build_sphinx_html.log')])
                                }
                                success{
                                    publishHTML([allowMissing: false, alwaysLinkToLastBuild: false, keepAll: false, reportDir: 'build/docs/html', reportFiles: 'index.html', reportName: 'Documentation', reportTitles: ''])
                                }
                                cleanup{
                                    cleanWs(
                                        notFailBuild: true,
                                        deleteDirs: true,
                                        patterns: [
                                            [pattern: 'build/', type: 'INCLUDE'],
                                        ]
                                    )
                                }
                            }
                        }
                    }
                }
                stage('Code Quality') {
                    agent {
                        dockerfile {
                            filename 'ci/docker/linux/jenkins/Dockerfile'
                            label 'linux && docker'
                            additionalBuildArgs '--build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL'
                        }
                    }
                    stages{
                        stage('Setting up'){
                            steps{
                                sh 'mkdir -p reports'
                            }
                        }
                        stage('Run Checks'){
                            parallel{
                                stage('pyDocStyle'){
                                    steps{
                                        catchError(buildResult: 'SUCCESS', message: 'Did not pass all pyDocStyle tests', stageResult: 'UNSTABLE') {
                                            sh(
                                                label: 'Run pydocstyle',
                                                script: '''mkdir -p reports
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
                                    steps{
                                        catchError(buildResult: 'UNSTABLE', message: 'Did not pass all pytest tests', stageResult: 'UNSTABLE') {
                                            sh(
                                                label: 'Running Pytest',
                                                script:'''mkdir -p reports/coverage
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
                                                    script: 'pylint uiucprescon.build -r n --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" > reports/pylint.txt'
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
                                               script: 'flake8 uiucprescon --tee --output-file=logs/flake8.log'
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
                                                script: '''mkdir -p logs
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
                                       script: '''coverage combine
                                                  coverage xml -o ./reports/coverage-python.xml
                                                  '''
                                    )
                                    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/coverage-python.xml'
                                    recordCoverage(tools: [[parser: 'COBERTURA', pattern: 'reports/coverage-python.xml']])
                                }
                            }
                        }
                    }
                    post{
                        cleanup{
                            cleanWs(
                                deleteDirs: true,
                                patterns: [
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
                    steps{
                        script{
                            def linuxJobs = [:]

                            def windowsJobs = [:]
                            def macJobs = [:]
                            parallel(
                                'Tox Information Gathering For: Linux': {
                                    if(nodesByLabel("linux && docker").size() > 0){
                                        linuxJobs = getToxTestsParallel(
                                            envNamePrefix: 'Tox Linux',
                                            label: 'linux && docker',
                                            dockerfile: 'ci/docker/linux/tox/Dockerfile',
                                            dockerArgs: '--build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL',
                                            dockerRunArgs: "-v pipcache_uiucprescon_build:/.cache/pip",
                                            verbosity: 1,
                                            retry: 2
                                        )
                                    } else {
                                        echo 'No nodes with the following labels: linux && docker labels'
                                    }
                                },
                                'Tox Information Gathering For: Windows': {
                                    if(nodesByLabel('windows && docker').size() > 0){
                                        windowsJobs = getToxTestsParallel(
                                            envNamePrefix: 'Tox Windows',
                                            label: 'windows && docker',
                                            dockerfile: 'ci/docker/windows/tox/Dockerfile',
                                            dockerArgs: '--build-arg PIP_EXTRA_INDEX_URL --build-arg PIP_INDEX_URL --build-arg CHOCOLATEY_SOURCE --build-arg chocolateyVersion --build-arg PIP_DOWNLOAD_CACHE=c:/users/containeradministrator/appdata/local/pip',
                                            dockerRunArgs: "-v pipcache_uiucprescon_build:c:/users/containeradministrator/appdata/local/pip",
                                            verbosity: 1,
                                            retry: 2
                                        )
                                    } else {
                                        echo 'No nodes with the following labels: windows && docker && x86'
                                    }
                                },
                                'Tox Information Gathering For: mac': {
                                    if(nodesByLabel('mac && python3').size() > 0){
                                        macJobs = macJobs + getMacToxTestsParallel(
                                          label: 'mac && python3', 
                                          envNamePrefix: 'Tox Mac',
                                          retry: 2
                                        )
                                    }
                                },
                             )

                            parallel(linuxJobs + windowsJobs + macJobs)
                        }
                    }
//                     post{
//                         failure{
//                             sh 'pip list'
//                         }
//                         cleanup{
//                             sh 'ls -aR'
//                         }
//                     }
                }
            }
        }
    }
}
