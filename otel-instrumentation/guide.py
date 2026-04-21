#!/usr/bin/env python3
"""
Guia interativo de instrumentaÃ§Ã£o OTel para LAS
"""

import os
import sys
from pathlib import Path

def print_banner():
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  ðŸš€ OpenTelemetry Auto-Instrumentador para LAS           â•‘
â•‘                                                            â•‘
â•‘  Instrumentalize suas aplicaÃ§Ãµes em qualquer linguagem     â•‘
â•‘  e envie mÃ©tricas para a plataforma LAS automaticamente  â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    """)

def print_menu():
    print("\nðŸ“‹ MENU PRINCIPAL\n")
    print("  1 - Instrumentar novo projeto")
    print("  2 - Ver exemplos de integraÃ§Ã£o")
    print("  3 - DocumentaÃ§Ã£o completa")
    print("  4 - Troubleshooting")
    print("  5 - Sair")
    print()

def show_quick_start():
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  âš¡ QUICK START                                             â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

Passo 1: Configure as credenciais LAS
   â€¢ Copie las-config.example.env para seu projeto
   â€¢ Edite com seu LAS_TOKEN e SERVICE_NAME

Passo 2: Execute a instrumentaÃ§Ã£o
   â€¢ Windows:  instrument.bat .
   â€¢ Linux/Mac: ./instrument.sh .
   â€¢ PowerShell: .\\instrument.ps1

Passo 3: Importe o mÃ³dulo OTel
   â€¢ Python:   import otel_init
   â€¢ Node.js:  require('./otel-init.js');
   â€¢ Java:     @Import(OTelConfig.class)
   â€¢ .NET:     builder.Services.AddLasOpenTelemetry();

Passo 4: Deploy e monitore!
   â€¢ Redeploy sua aplicaÃ§Ã£o
   â€¢ Verifique os traces no LAS

â±ï¸  Tempo total: ~5 minutos!
    """)

def show_examples():
    examples_path = Path(__file__).parent / 'examples'
    
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  ðŸ“š EXEMPLOS DISPONÃVEIS                                   â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    """)
    
    if examples_path.exists():
        for example in sorted(examples_path.glob('*')):
            print(f"  â€¢ {example.name}")
            print(f"    Veja: {example}")
    else:
        print("  âœ— Pasta de exemplos nÃ£o encontrada")

def show_languages():
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  ðŸ”§ LINGUAGENS SUPORTADAS                                  â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

  âœ“ Python (FastAPI, Django, Flask)
  âœ“ Node.js (Express, NestJS, Next.js)
  âœ“ Java (Spring Boot, Quarkus)
  âœ“ .NET (ASP.NET, C#)
  âœ“ PHP (Laravel, Symfony)

  + RUM (Real User Monitoring) para browser
    """)

def show_rum_info():
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  ðŸŽ¯ REAL USER MONITORING (RUM)                             â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

O RUM rastreia automaticamente:
  â€¢ ðŸ“Š Carregamento de pÃ¡gina
  â€¢ ðŸ–±ï¸  InteraÃ§Ãµes do usuÃ¡rio (cliques, formulÃ¡rios)
  â€¢ âš ï¸  Erros JavaScript
  â€¢ ðŸ”— NavegaÃ§Ã£o entre pÃ¡ginas
  â€¢ ðŸ“¡ RequisiÃ§Ãµes HTTP

Exemplos de uso:

  // Evento customizado
  nexusRUM.trackEvent('signup-completed', {
    'user.plan': 'pro',
    'signup.method': 'google'
  });

  // OperaÃ§Ã£o demorada
  await nexusRUM.trackOperation('fetch-data', async () => {
    return await fetch('/api/data');
  });

  // Contexto do usuÃ¡rio
  nexusRUM.setUserAttributes('user-123', {
    'user.email': 'user@example.com'
  });

Ativar RUM:
  instrument.bat . --enable-rum
    """)

def show_troubleshooting():
    print("""
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘  ðŸ› TROUBLESHOOTING                                         â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

âŒ "Failed to connect to LAS"
   âœ“ Verificar se LAS_TOKEN estÃ¡ correto
   âœ“ Verificar endpoint (padrÃ£o: api.soservices.com.br:8443)
   âœ“ Verificar firewall/proxy

âŒ "Traces nÃ£o aparecem no LAS"
   âœ“ Verificar se otel_init foi importado
   âœ“ Ativar DEBUG_MODE=true em .env
   âœ“ Executar: python instrument.py . 

âŒ "RUM nÃ£o funciona"
   âœ“ Verificar console do navegador (DevTools)
   âœ“ Verificar se app.js estÃ¡ sendo carregado
   âœ“ Verificar ENABLE_RUM=true em .env

âŒ "DependÃªncias nÃ£o instaladas"
   âœ“ Python: pip install -r requirements.txt
   âœ“ Node.js: npm install
   âœ“ .NET: dotnet restore
   âœ“ PHP: composer install

ðŸ’¡ Ativar debug:
   â€¢ DEBUG_MODE=true em .env
   â€¢ Traces serÃ£o exibidos no console
   â€¢ Ãštil para desenvolvimento

ðŸ“ž Suporte:
   â€¢ DocumentaÃ§Ã£o: https://LAS.soservices.com.br/docs
   â€¢ Issues: https://github.com/soservices/LAS/issues
    """)

def main():
    os.chdir(Path(__file__).parent)
    
    while True:
        print_banner()
        print_menu()
        
        choice = input("Escolha uma opÃ§Ã£o (1-5): ").strip()
        
        if choice == '1':
            print("\n" + "="*60)
            show_quick_start()
            input("\nPressione ENTER para continuar...")
            os.system('clear' if os.name == 'posix' else 'cls')
            
        elif choice == '2':
            print("\n" + "="*60)
            show_examples()
            print("\nVocÃª tambÃ©m pode:")
            print("  â€¢ Ver RUM info (opÃ§Ã£o 3)")
            print("  â€¢ Exibir linguagens suportadas (prÃ³ximo menu)")
            input("\nPressione ENTER para continuar...")
            os.system('clear' if os.name == 'posix' else 'cls')
            
        elif choice == '3':
            print("\n" + "="*60)
            show_languages()
            print("\n" + "-"*60)
            show_rum_info()
            input("\nPressione ENTER para continuar...")
            os.system('clear' if os.name == 'posix' else 'cls')
            
        elif choice == '4':
            print("\n" + "="*60)
            show_troubleshooting()
            input("\nPressione ENTER para continuar...")
            os.system('clear' if os.name == 'posix' else 'cls')
            
        elif choice == '5':
            print("\nâœ“ AtÃ© logo! ðŸ‘‹\n")
            break
            
        else:
            print("\nâœ— OpÃ§Ã£o invÃ¡lida")
            input("Pressione ENTER para continuar...")
            os.system('clear' if os.name == 'posix' else 'cls')

if __name__ == '__main__':
    main()

