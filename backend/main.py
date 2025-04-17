import os
import sys
import argparse
import subprocess
import threading
import time

def run_backend():
    """Executa o servidor backend"""
    print("Iniciando servidor backend...")
    subprocess.run([sys.executable, "app.py"])

def run_dashboard():
    """Executa o dashboard Streamlit"""
    print("Iniciando dashboard...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py"])

def import_data(csv_file):
    """Importa dados do CSV para o MongoDB"""
    print(f"Importando dados de {csv_file}...")
    subprocess.run([sys.executable, "import_csv.py", csv_file])

def main():
    parser = argparse.ArgumentParser(description="Sistema de Monitoramento de Temperatura e Umidade")
    parser.add_argument("--import", dest="import_file", nargs='?', const='dht11_simulated_data_90days.csv',
                      help="Importar dados de um arquivo CSV (opcional)")
    parser.add_argument("--backend", action="store_true", help="Iniciar apenas o servidor backend")
    parser.add_argument("--dashboard", action="store_true", help="Iniciar apenas o dashboard")
    parser.add_argument("--all", action="store_true", help="Iniciar backend e dashboard")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    if args.import_file:
        import_data(args.import_file)
        
    if args.backend or args.all:
        backend_thread = threading.Thread(target=run_backend)
        backend_thread.daemon = True
        backend_thread.start()
        
        if args.all:
            time.sleep(2)
    
    if args.dashboard or args.all:
        run_dashboard()
        
    if args.all:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nEncerrando o sistema...")
            sys.exit(0)

if __name__ == "__main__":
    main()