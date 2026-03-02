"""
VectorShield CLI
"""
import sys
import argparse
import asyncio
import json
from pathlib import Path
from . import IngestionPipeline, Document, load_config, __version__


def cmd_process(args):
    """Process documents from file or stdin."""
    
    async def process():
        # Load config
        config = load_config(config_file=args.config) if args.config else None
        
        # Initialize pipeline
        pipeline = IngestionPipeline(config=config)
        await pipeline.initialize()
        
        # Load documents
        if args.input == '-':
            # Read from stdin
            data = json.load(sys.stdin)
        else:
            # Read from file
            with open(args.input) as f:
                data = json.load(f)
        
        # Process
        docs = [Document(**doc) for doc in data.get('documents', [])]
        result = await pipeline.process_batch(docs)
        
        # Output
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result, indent=2))
        
        # Stats
        if args.stats:
            stats = pipeline.get_metrics()
            print("\n📊 Statistics:", file=sys.stderr)
            print(json.dumps(stats, indent=2), file=sys.stderr)
        
        await pipeline.shutdown()
    
    asyncio.run(process())


def cmd_version(args):
    """Show version."""
    print(f"VectorShield v{__version__}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="VectorShield - Privacy-Preserving RAG Middleware",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process documents')
    process_parser.add_argument(
        '-i', '--input',
        default='-',
        help='Input JSON file (use - for stdin)'
    )
    process_parser.add_argument(
        '-o', '--output',
        help='Output JSON file (default: stdout)'
    )
    process_parser.add_argument(
        '-c', '--config',
        help='Config YAML file'
    )
    process_parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics'
    )
    process_parser.set_defaults(func=cmd_process)
    
    # Version command
    version_parser = subparsers.add_parser('version', help='Show version')
    version_parser.set_defaults(func=cmd_version)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()