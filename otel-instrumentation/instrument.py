#!/usr/bin/env python3
"""
Auto-Instrumentador OpenTelemetry para LAS
Detecta linguagem, tipo de projeto e instrumenta automaticamente
"""

import os
import sys
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Carregar configuração
load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent / "las-config.example.env", override=False)

class OTelInstrumentor:
    def __init__(self, project_path: str, enable_rum: bool = True):
        self.project_path = Path(project_path)
        self.enable_rum = enable_rum
        self.detected_language = None
        self.detected_framework = None
        
    def detect_language(self) -> str:
        """Detecta linguagem do projeto"""
        detectors = {
            'java': ['pom.xml', 'build.gradle', '.jar'],
            'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
            'nodejs': ['package.json', 'package-lock.json'],
            'dotnet': ['.csproj', '.vbproj', '.sln'],
            'php': ['composer.json', 'index.php'],
        }
        
        for lang, patterns in detectors.items():
            for pattern in patterns:
                if list(self.project_path.rglob(pattern)):
                    self.detected_language = lang
                    print(f"✓ Linguagem detectada: {lang.upper()}")
                    return lang
        
        print("✗ Linguagem não identificada")
        return None
    
    def detect_framework(self) -> str:
        """Detecta framework usado"""
        frameworks = {
            'python': {
                'fastapi': 'fastapi',
                'django': 'django',
                'flask': 'flask',
            },
            'nodejs': {
                'express': 'express',
                'nestjs': 'nestjs',
            },
            'java': {
                'spring-boot': 'spring',
                'quarkus': 'quarkus',
            },
            'dotnet': {
                'asp.net': 'aspnet',
            },
            'php': {
                'laravel': 'laravel',
                'symfony': 'symfony',
            }
        }
        
        if not self.detected_language:
            return None
        
        # Ler arquivo de dependências
        if self.detected_language == 'python':
            req_file = self.project_path / 'requirements.txt'
            if req_file.exists():
                content = req_file.read_text()
                for framework, key in frameworks['python'].items():
                    if key in content:
                        self.detected_framework = framework
                        print(f"✓ Framework detectado: {framework}")
                        return framework
        
        elif self.detected_language == 'nodejs':
            pkg_file = self.project_path / 'package.json'
            if pkg_file.exists():
                try:
                    content = json.load(open(pkg_file))
                    deps = content.get('dependencies', {})
                    for framework, key in frameworks['nodejs'].items():
                        if key in deps:
                            self.detected_framework = framework
                            print(f"✓ Framework detectado: {framework}")
                            return framework
                except:
                    pass
        
        return None
    
    def instrument(self):
        """Executa instrumentação baseada na linguagem"""
        if not self.detect_language():
            print("\n❌ Falha: Linguagem não identificada")
            return False
        
        self.detect_framework()
        
        method_name = f'instrument_{self.detected_language}'
        if hasattr(self, method_name):
            getattr(self, method_name)()
            print(f"\n✓ Instrumentação {self.detected_language.upper()} concluída!")
            return True
        
        print(f"✗ Suporte para {self.detected_language} não disponível")
        return False
    
    def instrument_python(self):
        """Instrumenta aplicação Python"""
        print("\n📦 Instrumentando Python...")
        
        # Atualizar requirements.txt
        req_file = self.project_path / 'requirements.txt'
        otel_packages = [
            'opentelemetry-sdk>=1.20.0',
            'opentelemetry-exporter-otlp>=0.41b0',
            'opentelemetry-api>=1.20.0',
            'opentelemetry-sdk-resources>=0.41b0',
        ]
        
        if self.detected_framework == 'fastapi':
            otel_packages.append('opentelemetry-instrumentation-fastapi>=0.41b0')
        elif self.detected_framework == 'django':
            otel_packages.append('opentelemetry-instrumentation-django>=0.41b0')
        elif self.detected_framework == 'flask':
            otel_packages.append('opentelemetry-instrumentation-flask>=0.41b0')
        
        if req_file.exists():
            existing = req_file.read_text()
            for package in otel_packages:
                if package.split('>=')[0] not in existing:
                    existing += f"\n{package}"
            req_file.write_text(existing)
            print(f"✓ requirements.txt atualizado")
        
        # Copiar arquivo de inicialização OTel
        otel_init = self.project_path / 'otel_init.py'
        template = Path(__file__).parent / 'templates/python/otel_init.py'
        if template.exists():
            shutil.copy(template, otel_init)
            print(f"✓ otel_init.py criado")
    
    def instrument_nodejs(self):
        """Instrumenta aplicação Node.js"""
        print("\n📦 Instrumentando Node.js...")
        
        # Atualizar package.json
        pkg_file = self.project_path / 'package.json'
        if pkg_file.exists():
            try:
                with open(pkg_file, 'r') as f:
                    pkg = json.load(f)
                
                otel_deps = {
                    '@opentelemetry/sdk-node': '^0.45.0',
                    '@opentelemetry/auto-instrumentations-node': '^0.39.1',
                    '@opentelemetry/sdk-trace-node': '^0.45.0',
                    '@opentelemetry/exporter-trace-otlp-http': '^0.45.0',
                }
                
                if 'dependencies' not in pkg:
                    pkg['dependencies'] = {}
                
                pkg['dependencies'].update(otel_deps)
                
                with open(pkg_file, 'w') as f:
                    json.dump(pkg, f, indent=2)
                
                print(f"✓ package.json atualizado")
                
                # Copiar arquivo de inicialização
                otel_init = self.project_path / 'otel-init.js'
                template = Path(__file__).parent / 'templates/nodejs/otel-init.js'
                if template.exists():
                    shutil.copy(template, otel_init)
                    print(f"✓ otel-init.js criado")
            except Exception as e:
                print(f"✗ Erro ao atualizar package.json: {e}")
    
    def instrument_java(self):
        """Instrumenta aplicação Java"""
        print("\n📦 Instrumentando Java...")
        template = Path(__file__).parent / 'templates/java/OTelConfig.java'
        if template.exists():
            target = self.project_path / 'src/main/java/com/las/OTelConfig.java'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(template, target)
            print(f"✓ OTelConfig.java criado")
    
    def instrument_dotnet(self):
        """Instrumenta aplicação .NET"""
        print("\n📦 Instrumentando .NET...")
        template = Path(__file__).parent / 'templates/dotnet/OTelConfig.cs'
        if template.exists():
            target = self.project_path / 'OTelConfig.cs'
            shutil.copy(template, target)
            print(f"✓ OTelConfig.cs criado")
    
    def instrument_php(self):
        """Instrumenta aplicação PHP"""
        print("\n📦 Instrumentando PHP...")
        template = Path(__file__).parent / 'templates/php/otel-init.php'
        if template.exists():
            target = self.project_path / 'otel-init.php'
            shutil.copy(template, target)
            print(f"✓ otel-init.php criado")
    
    def add_rum(self):
        """Adiciona instrumentação RUM (Real User Monitoring)"""
        if not self.enable_rum:
            return
        
        print("\n🎯 Adicionando RUM...")
        
        if self.detected_language == 'nodejs' or self.detected_language == 'python':
            rum_js = self.project_path / 'public/app.js'
            rum_js.parent.mkdir(parents=True, exist_ok=True)
            
            template = Path(__file__).parent / 'rum/app.js'
            if template.exists():
                shutil.copy(template, rum_js)
                print(f"✓ app.js (RUM) criado")

def main():
    if len(sys.argv) < 2:
        print("""
╔════════════════════════════════════════════╗
║   OpenTelemetry Auto-Instrumentador        ║
║   para LAS                                ║
╚════════════════════════════════════════════╝

Uso: python instrument.py <caminho_do_projeto> [--enable-rum] [--disable-rum]

Exemplos:
  python instrument.py .
  python instrument.py /path/to/my-app --enable-rum
  python instrument.py ./backend --disable-rum
        """)
        return
    
    project_path = sys.argv[1]
    enable_rum = '--disable-rum' not in sys.argv
    
    if not Path(project_path).exists():
        print(f"✗ Caminho não encontrado: {project_path}")
        return
    
    instrumentor = OTelInstrumentor(project_path, enable_rum=enable_rum)
    
    print(f"\n📍 Inspecionando: {project_path}")
    print(f"🎯 RUM: {'ATIVADO' if enable_rum else 'DESATIVADO'}")
    
    success = instrumentor.instrument()
    
    if success:
        if enable_rum:
            instrumentor.add_rum()
        print("\n✅ Instrumentação concluída com sucesso!")
        print("\nPróximos passos:")
        print("1. Execute: pip install -r requirements.txt  (or npm install)")
        print("2. Importe otel_init no seu main.py (ou carregue otel-init.js)")
        print("3. Redeploy sua aplicação")
    else:
        print("\n❌ Instrumentação falhou")

if __name__ == '__main__':
    main()
