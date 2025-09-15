chmod +x scripts/vegeta_step_attack.sh scripts/vegeta_parse_report.py
echo made executable
./scripts/vegeta_step_attack.sh -t vegeta_targets.txt -r "50,100,150,200,250,300,350,360,375,390,400,425,450" -d 30 -o ./vegeta_step_runs -p load_test 
ls -l vegeta_step_runs | sed -n '1,200p'