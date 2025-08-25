#!/usr/bin/env python3
"""
Lab Protocol Optimizer
A tool that analyzes lab protocols and suggests optimizations for cost and time reduction
using Gemini API and public repository data.
"""

import os
import json
import re
import time
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import argparse
import sys

# Install required packages: pip install requests beautifulsoup4 pandas

try:
    import pandas as pd
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing required packages...")
    os.system("pip install requests beautifulsoup4 pandas")
    import pandas as pd
    from bs4 import BeautifulSoup

@dataclass
class Optimization:
    """Represents a protocol optimization suggestion"""
    type: str
    suggestion: str
    savings: str
    confidence: float
    source: str
    estimated_cost_reduction: float = 0.0
    estimated_time_reduction: float = 0.0

@dataclass
class Protocol:
    """Represents a lab protocol"""
    title: str
    description: str
    materials: List[str]
    steps: List[str]
    estimated_cost: float = 0.0
    estimated_time: float = 0.0
    constraints: str = ""

class ProtocolDatabase:
    """Mock database simulating protocol repositories"""
    
    def __init__(self):
        self.protocols = {
            'pcr': {
                'keywords': ['pcr', 'amplification', 'polymerase', 'thermocycler'],
                'optimizations': [
                    {
                        'type': 'Time Reduction',
                        'suggestion': 'Use fast polymerase (Phusion Flash) to reduce extension time from 1min/kb to 15sec/kb',
                        'savings': '75% cycle time reduction',
                        'confidence': 0.9,
                        'source': 'protocols.io/pcr-optimization-2023',
                        'cost_reduction': 0.0,
                        'time_reduction': 0.75
                    },
                    {
                        'type': 'Cost Reduction',
                        'suggestion': 'Reduce reaction volume from 50μl to 20μl. Use nested PCR design if sensitivity is needed',
                        'savings': '60% reagent cost reduction',
                        'confidence': 0.85,
                        'source': 'github.com/lab-protocols/pcr-miniaturization',
                        'cost_reduction': 0.6,
                        'time_reduction': 0.0
                    },
                    {
                        'type': 'Efficiency Enhancement',
                        'suggestion': 'Add touchdown PCR protocol to improve specificity and reduce optimization time',
                        'savings': '50% optimization time reduction',
                        'confidence': 0.8,
                        'source': 'bio-protocol.org/touchdown-pcr',
                        'cost_reduction': 0.1,
                        'time_reduction': 0.3
                    }
                ]
            },
            'western_blot': {
                'keywords': ['western', 'blot', 'sds-page', 'immunoblot', 'antibody'],
                'optimizations': [
                    {
                        'type': 'Time Reduction',
                        'suggestion': 'Use rapid transfer system (iBlot) instead of wet transfer: 7min vs 2hr',
                        'savings': '95% transfer time reduction',
                        'confidence': 0.9,
                        'source': 'protocols.io/rapid-western-transfer',
                        'cost_reduction': 0.0,
                        'time_reduction': 0.95
                    },
                    {
                        'type': 'Cost Reduction',
                        'suggestion': 'Strip and reuse PVDF membranes up to 3 times with mild stripping buffer',
                        'savings': '70% membrane cost reduction',
                        'confidence': 0.75,
                        'source': 'jove.com/membrane-reuse-protocols',
                        'cost_reduction': 0.7,
                        'time_reduction': 0.0
                    }
                ]
            },
            'cell_culture': {
                'keywords': ['cell culture', 'culture', 'media', 'passage', 'culture flask'],
                'optimizations': [
                    {
                        'type': 'Cost Reduction',
                        'suggestion': 'Switch to serum-free media (OptiMEM, PowerMed) - reduces cost and variability',
                        'savings': '40-60% media cost reduction',
                        'confidence': 0.8,
                        'source': 'cell-culture-protocols.org/serum-free-2023',
                        'cost_reduction': 0.5,
                        'time_reduction': 0.1
                    },
                    {
                        'type': 'Automation',
                        'suggestion': 'Use automated cell counting (Countess) instead of manual hemocytometer',
                        'savings': '80% counting time reduction',
                        'confidence': 0.9,
                        'source': 'github.com/lab-automation/cell-counting',
                        'cost_reduction': 0.0,
                        'time_reduction': 0.8
                    }
                ]
            },
            'elisa': {
                'keywords': ['elisa', 'enzyme-linked', 'immunoassay', 'plate reader'],
                'optimizations': [
                    {
                        'type': 'Cost Reduction',
                        'suggestion': 'Use half-volume (50μl) ELISA protocol in 384-well plates',
                        'savings': '50% reagent cost, 4x throughput',
                        'confidence': 0.85,
                        'source': 'protocols.io/miniaturized-elisa',
                        'cost_reduction': 0.5,
                        'time_reduction': 0.3
                    }
                ]
            },
            'qpcr': {
                'keywords': ['qpcr', 'real-time pcr', 'quantitative pcr', 'sybr', 'taqman'],
                'optimizations': [
                    {
                        'type': 'Cost Reduction',
                        'suggestion': 'Use SYBR Green instead of TaqMan probes where possible (10x cost reduction)',
                        'savings': '90% detection cost reduction',
                        'confidence': 0.7,
                        'source': 'qpcr-protocols.org/sybr-optimization',
                        'cost_reduction': 0.9,
                        'time_reduction': 0.0
                    }
                ]
            }
        }

    def get_optimizations(self, protocol_text: str) -> List[Dict]:
        """Get optimizations based on protocol content"""
        protocol_text_lower = protocol_text.lower()
        found_optimizations = []
        
        for protocol_type, data in self.protocols.items():
            # Check if any keywords match
            if any(keyword in protocol_text_lower for keyword in data['keywords']):
                found_optimizations.extend(data['optimizations'])
        
        return found_optimizations

class GeminiOptimizer:
    """Interface to Gemini API for protocol optimization"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    def optimize_protocol(self, protocol: Protocol) -> List[Optimization]:
        """Get optimization suggestions from Gemini API"""
        
        prompt = f"""
        As an expert lab protocol optimizer, analyze this protocol and provide specific optimizations:
        
        PROTOCOL DETAILS:
        Title: {protocol.title}
        Description: {protocol.description}
        Materials: {', '.join(protocol.materials) if protocol.materials else 'Not specified'}
        Constraints: {protocol.constraints}
        
        TASK: Provide 3-5 specific, actionable optimizations focusing on:
        1. Cost reduction (cheaper alternatives, volume reduction, bulk purchasing)
        2. Time reduction (faster methods, parallel processing, automation)
        3. Efficiency improvements (better yields, reduced errors, simplified steps)
        4. Equipment alternatives (cheaper/more available instruments)
        
        FORMAT EACH OPTIMIZATION AS:
        TYPE: [Cost Reduction|Time Reduction|Efficiency|Equipment]
        SUGGESTION: [Specific actionable recommendation]
        SAVINGS: [Quantified benefit]
        CONFIDENCE: [0.1-1.0 confidence score]
        REASONING: [Brief scientific justification]
        ---
        
        Be specific with numbers, brands, and techniques. Focus on practical, immediately implementable changes.
        """
        
        try:
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                json={
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 2048
                    }
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code} - {response.text}")
            
            data = response.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            
            return self._parse_gemini_response(text)
            
        except Exception as e:
            print(f"Warning: Gemini API error: {e}")
            return []
    
    def _parse_gemini_response(self, text: str) -> List[Optimization]:
        """Parse Gemini response into structured optimizations"""
        optimizations = []
        sections = text.split('---')
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            # Extract fields using regex
            type_match = re.search(r'TYPE:\s*(.+)', section, re.IGNORECASE)
            suggestion_match = re.search(r'SUGGESTION:\s*(.+)', section, re.IGNORECASE | re.DOTALL)
            savings_match = re.search(r'SAVINGS:\s*(.+)', section, re.IGNORECASE)
            confidence_match = re.search(r'CONFIDENCE:\s*([\d.]+)', section, re.IGNORECASE)
            
            if type_match and suggestion_match:
                # Clean up suggestion text
                suggestion_text = suggestion_match.group(1).strip()
                suggestion_text = re.sub(r'SAVINGS:.*', '', suggestion_text, flags=re.IGNORECASE | re.DOTALL).strip()
                
                optimization = Optimization(
                    type=type_match.group(1).strip(),
                    suggestion=suggestion_text,
                    savings=savings_match.group(1).strip() if savings_match else "Variable",
                    confidence=float(confidence_match.group(1)) if confidence_match else 0.7,
                    source="Gemini AI Analysis",
                    estimated_cost_reduction=self._extract_cost_reduction(section),
                    estimated_time_reduction=self._extract_time_reduction(section)
                )
                optimizations.append(optimization)
        
        return optimizations[:5]  # Limit to 5 optimizations
    
    def _extract_cost_reduction(self, text: str) -> float:
        """Extract estimated cost reduction percentage from text"""
        cost_patterns = [
            r'(\d+)%.*cost.*reduction',
            r'(\d+)%.*cheaper',
            r'save.*(\d+)%.*cost',
            r'reduce.*cost.*(\d+)%'
        ]
        
        for pattern in cost_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1)) / 100
        return 0.0
    
    def _extract_time_reduction(self, text: str) -> float:
        """Extract estimated time reduction percentage from text"""
        time_patterns = [
            r'(\d+)%.*time.*reduction',
            r'(\d+)%.*faster',
            r'save.*(\d+)%.*time',
            r'reduce.*time.*(\d+)%'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1)) / 100
        return 0.0

class ProtocolOptimizer:
    """Main protocol optimization engine"""
    
    def __init__(self, gemini_api_key: str):
        self.db = ProtocolDatabase()
        self.gemini = GeminiOptimizer(gemini_api_key) if gemini_api_key else None
        
    def analyze_protocol(self, protocol: Protocol) -> Dict:
        """Analyze protocol and return optimizations"""
        
        print(f"🔍 Analyzing protocol: {protocol.title}")
        print("=" * 60)
        
        # Get database optimizations
        db_optimizations = self.db.get_optimizations(
            f"{protocol.title} {protocol.description} {' '.join(protocol.materials)}"
        )
        
        # Convert to Optimization objects
        db_opts = []
        for opt_data in db_optimizations:
            db_opts.append(Optimization(
                type=opt_data['type'],
                suggestion=opt_data['suggestion'],
                savings=opt_data['savings'],
                confidence=opt_data['confidence'],
                source=opt_data['source'],
                estimated_cost_reduction=opt_data.get('cost_reduction', 0.0),
                estimated_time_reduction=opt_data.get('time_reduction', 0.0)
            ))
        
        # Get Gemini optimizations
        gemini_opts = []
        if self.gemini:
            print("🤖 Consulting Gemini AI...")
            gemini_opts = self.gemini.optimize_protocol(protocol)
        
        # Combine and rank optimizations
        all_optimizations = db_opts + gemini_opts
        all_optimizations.sort(key=lambda x: x.confidence, reverse=True)
        
        # Calculate aggregate savings
        total_cost_reduction = min(sum(opt.estimated_cost_reduction for opt in all_optimizations), 0.8)
        total_time_reduction = min(sum(opt.estimated_time_reduction for opt in all_optimizations), 0.9)
        
        return {
            'optimizations': all_optimizations,
            'total_cost_reduction': total_cost_reduction,
            'total_time_reduction': total_time_reduction,
            'optimization_count': len(all_optimizations),
            'average_confidence': sum(opt.confidence for opt in all_optimizations) / len(all_optimizations) if all_optimizations else 0
        }

class ProtocolReportGenerator:
    """Generate optimization reports"""
    
    @staticmethod
    def print_results(results: Dict, protocol: Protocol):
        """Print optimization results to console"""
        
        print(f"\n📊 OPTIMIZATION RESULTS FOR: {protocol.title}")
        print("=" * 80)
        
        print(f"📈 SUMMARY:")
        print(f"   • Optimizations Found: {results['optimization_count']}")
        print(f"   • Estimated Cost Reduction: {results['total_cost_reduction']:.1%}")
        print(f"   • Estimated Time Reduction: {results['total_time_reduction']:.1%}")
        print(f"   • Average Confidence: {results['average_confidence']:.1%}")
        
        print(f"\n🚀 DETAILED OPTIMIZATIONS:")
        print("-" * 80)
        
        for i, opt in enumerate(results['optimizations'], 1):
            print(f"\n{i}. {opt.type.upper()}")
            print(f"   💡 Suggestion: {opt.suggestion}")
            print(f"   💰 Savings: {opt.savings}")
            print(f"   🎯 Confidence: {opt.confidence:.1%}")
            print(f"   📚 Source: {opt.source}")
            
            if opt.estimated_cost_reduction > 0:
                print(f"   💵 Est. Cost Reduction: {opt.estimated_cost_reduction:.1%}")
            if opt.estimated_time_reduction > 0:
                print(f"   ⏱️  Est. Time Reduction: {opt.estimated_time_reduction:.1%}")
        
        print("\n" + "=" * 80)
    
    @staticmethod
    def save_to_file(results: Dict, protocol: Protocol, filename: str = None):
        """Save results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"protocol_optimization_{timestamp}.json"
        
        data = {
            'protocol': {
                'title': protocol.title,
                'description': protocol.description,
                'materials': protocol.materials,
                'constraints': protocol.constraints,
                'timestamp': datetime.now().isoformat()
            },
            'results': {
                'optimization_count': results['optimization_count'],
                'total_cost_reduction': results['total_cost_reduction'],
                'total_time_reduction': results['total_time_reduction'],
                'average_confidence': results['average_confidence'],
                'optimizations': [
                    {
                        'type': opt.type,
                        'suggestion': opt.suggestion,
                        'savings': opt.savings,
                        'confidence': opt.confidence,
                        'source': opt.source,
                        'estimated_cost_reduction': opt.estimated_cost_reduction,
                        'estimated_time_reduction': opt.estimated_time_reduction
                    }
                    for opt in results['optimizations']
                ]
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"📄 Results saved to: {filename}")

def interactive_mode():
    """Interactive mode for protocol input"""
    print("🧪 LAB PROTOCOL OPTIMIZER")
    print("=" * 50)
    print("Enter your protocol details below:")
    
    title = input("Protocol Title: ").strip()
    description = input("Protocol Description: ").strip()
    
    materials = []
    print("\nMaterials (press Enter on empty line to finish):")
    while True:
        material = input("  - ").strip()
        if not material:
            break
        materials.append(material)
    
    constraints = input("Budget/Time Constraints (optional): ").strip()
    
    api_key = input("\nGemini API Key (optional, get free key from https://makersuite.google.com/app/apikey): ").strip()
    
    return Protocol(title, description, materials, [], constraints=constraints), api_key

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='Lab Protocol Optimizer')
    parser.add_argument('--title', help='Protocol title')
    parser.add_argument('--description', help='Protocol description')
    parser.add_argument('--materials', nargs='*', help='List of materials')
    parser.add_argument('--constraints', help='Budget/time constraints')
    parser.add_argument('--api-key', help='Gemini API key')
    parser.add_argument('--save', help='Save results to file')
    parser.add_argument('--interactive', action='store_true', help='Run in interactive mode')
    
    args = parser.parse_args()
    
    try:
        if args.interactive or not args.title:
            protocol, api_key = interactive_mode()
        else:
            protocol = Protocol(
                title=args.title,
                description=args.description or "",
                materials=args.materials or [],
                steps=[],
                constraints=args.constraints or ""
            )
            api_key = args.api_key or os.getenv('GEMINI_API_KEY')
        
        # Initialize optimizer
        optimizer = ProtocolOptimizer(api_key)
        
        # Analyze protocol
        results = optimizer.analyze_protocol(protocol)
        
        # Display results
        ProtocolReportGenerator.print_results(results, protocol)
        
        # Save if requested
        if args.save:
            ProtocolReportGenerator.save_to_file(results, protocol, args.save)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()