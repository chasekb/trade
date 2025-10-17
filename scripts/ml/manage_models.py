#!/usr/bin/env python3
"""ML Model Management Script for Trading Optimization."""

import logging
import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from trade_bot.ml.model_manager import ModelManager
from trade_bot.ml.ml_optimizer import MLTradingOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'outputs/ml_model_management_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MLModelManagerCLI:
    """Command-line interface for ML model management."""
    
    def __init__(self, models_dir: str = "data/models"):
        self.models_dir = models_dir
        self.model_manager = ModelManager(models_dir)
        self.ml_optimizer = MLTradingOptimizer(models_dir=models_dir)
    
    def list_models(self):
        """List all registered models."""
        logger.info("Listing all registered models...")
        
        models = self.model_manager.list_models()
        
        if not models:
            print("No models registered.")
            return
        
        print("\n" + "="*80)
        print("REGISTERED MODELS")
        print("="*80)
        
        for model in models:
            print(f"\nModel: {model['model_name']}")
            print(f"  Versions: {model['versions']}")
            print(f"  Latest Version: {model['latest_version']}")
            print(f"  Status: {model['status']}")
            
            if model['latest_performance']:
                print(f"  Latest Performance:")
                for metric, value in model['latest_performance'].items():
                    if isinstance(value, float):
                        print(f"    {metric}: {value:.4f}")
                    else:
                        print(f"    {metric}: {value}")
    
    def show_current_model(self):
        """Show information about the currently deployed model."""
        logger.info("Getting current model information...")
        
        current_model = self.model_manager.get_current_model()
        
        if not current_model:
            print("No model currently deployed.")
            return
        
        print("\n" + "="*80)
        print("CURRENT DEPLOYED MODEL")
        print("="*80)
        
        print(f"Model Name: {current_model['model_name']}")
        print(f"Version ID: {current_model['version_id']}")
        print(f"Deployed At: {current_model['deployed_at']}")
        
        if current_model['performance_metrics']:
            print(f"Performance Metrics:")
            for metric, value in current_model['performance_metrics'].items():
                if isinstance(value, float):
                    print(f"  {metric}: {value:.4f}")
                else:
                    print(f"  {metric}: {value}")
    
    def deploy_model(self, model_name: str, version_id: str = None):
        """Deploy a specific model version."""
        logger.info(f"Deploying model {model_name} version {version_id or 'latest'}...")
        
        success = self.model_manager.deploy_model(model_name, version_id)
        
        if success:
            print(f"✅ Successfully deployed {model_name} version {version_id or 'latest'}")
        else:
            print(f"❌ Failed to deploy {model_name} version {version_id or 'latest'}")
    
    def rollback_model(self, model_name: str):
        """Rollback to the previous model version."""
        logger.info(f"Rolling back {model_name} to previous version...")
        
        success = self.model_manager.rollback_model(model_name)
        
        if success:
            print(f"✅ Successfully rolled back {model_name}")
        else:
            print(f"❌ Failed to rollback {model_name}")
    
    def evaluate_model(self, test_data_path: str = None):
        """Evaluate the current model's performance."""
        logger.info("Evaluating current model performance...")
        
        if not test_data_path:
            # Use recent data for evaluation
            logger.info("Using recent trading data for evaluation...")
            features, outcomes = self.ml_optimizer.collect_and_preprocess_data(days_back=7)
            
            if not features or not outcomes:
                print("❌ No recent data available for evaluation")
                return
            
            # Create test data
            X, y, _ = self.ml_optimizer.feature_engineer.create_feature_matrix(features, outcomes)
            if X.shape[0] == 0:
                print("❌ No valid test data created")
                return
            
            X_test = self.ml_optimizer.feature_engineer.preprocess_pipeline(X, y, fit_transform=False)
        else:
            # Load test data from file
            logger.info(f"Loading test data from {test_data_path}...")
            # Implementation would depend on test data format
            print("❌ Test data file loading not implemented yet")
            return
        
        # Evaluate model
        performance = self.model_manager.evaluate_model_performance(X_test, y)
        
        if performance:
            print("\n" + "="*80)
            print("MODEL EVALUATION RESULTS")
            print("="*80)
            
            for metric, value in performance.items():
                if isinstance(value, float):
                    print(f"{metric}: {value:.4f}")
                else:
                    print(f"{metric}: {value}")
        else:
            print("❌ Model evaluation failed")
    
    def cleanup_old_versions(self, model_name: str, keep_versions: int = 5):
        """Clean up old model versions."""
        logger.info(f"Cleaning up old versions for {model_name}, keeping {keep_versions}...")
        
        success = self.model_manager.cleanup_old_versions(model_name, keep_versions)
        
        if success:
            print(f"✅ Successfully cleaned up old versions for {model_name}")
        else:
            print(f"❌ Failed to cleanup old versions for {model_name}")
    
    def get_performance_history(self, model_name: str = None):
        """Get performance history for models."""
        logger.info("Getting performance history...")
        
        performance = self.model_manager.get_model_performance(model_name)
        
        if not performance:
            print("No performance data available.")
            return
        
        print("\n" + "="*80)
        print("PERFORMANCE HISTORY")
        print("="*80)
        
        if model_name:
            # Single model performance
            print(f"\nModel: {model_name}")
            print(f"Versions: {performance.get('versions', 0)}")
            
            if performance.get('latest_performance'):
                print("Latest Performance:")
                for metric, value in performance['latest_performance'].items():
                    if isinstance(value, float):
                        print(f"  {metric}: {value:.4f}")
                    else:
                        print(f"  {metric}: {value}")
            
            if performance.get('performance_history'):
                print(f"\nPerformance History ({len(performance['performance_history'])} versions):")
                for i, perf in enumerate(performance['performance_history'][-5:]):  # Show last 5
                    print(f"  Version {i+1}: R² = {perf.get('r2', 0):.4f}, RMSE = {perf.get('rmse', 0):.4f}")
        else:
            # All models performance
            for model_name, perf_data in performance.items():
                print(f"\nModel: {model_name}")
                print(f"  Versions: {perf_data.get('versions', 0)}")
                if perf_data.get('latest_performance'):
                    latest = perf_data['latest_performance']
                    print(f"  Latest R²: {latest.get('r2', 0):.4f}")
                    print(f"  Latest RMSE: {latest.get('rmse', 0):.4f}")
    
    def export_model(self, model_name: str, version_id: str, output_path: str):
        """Export a model to a file."""
        logger.info(f"Exporting {model_name} version {version_id} to {output_path}...")
        
        # Find the model version
        model_version = None
        for model in self.model_manager.model_versions.get(model_name, []):
            if model['version_id'] == version_id:
                model_version = model
                break
        
        if not model_version:
            print(f"❌ Model version {model_name}:{version_id} not found")
            return
        
        try:
            import shutil
            shutil.copy2(model_version['model_path'], output_path)
            print(f"✅ Successfully exported model to {output_path}")
        except Exception as e:
            print(f"❌ Failed to export model: {e}")
    
    def import_model(self, model_path: str, model_name: str, performance_metrics: dict = None):
        """Import a model from a file."""
        logger.info(f"Importing model from {model_path}...")
        
        if not os.path.exists(model_path):
            print(f"❌ Model file {model_path} not found")
            return
        
        try:
            # Register the imported model
            version_id = self.model_manager.register_model(
                model_name=model_name,
                model_path=model_path,
                performance_metrics=performance_metrics or {},
                metadata={'imported': True, 'imported_at': datetime.now().isoformat()}
            )
            
            if version_id:
                print(f"✅ Successfully imported model as {model_name} version {version_id}")
            else:
                print(f"❌ Failed to import model")
                
        except Exception as e:
            print(f"❌ Error importing model: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='ML Model Management CLI')
    parser.add_argument('--models-dir', type=str, default='data/models',
                       help='Directory containing model files')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List models command
    subparsers.add_parser('list', help='List all registered models')
    
    # Show current model command
    subparsers.add_parser('current', help='Show current deployed model')
    
    # Deploy model command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy a model version')
    deploy_parser.add_argument('model_name', help='Name of the model to deploy')
    deploy_parser.add_argument('--version', help='Version ID to deploy (default: latest)')
    
    # Rollback model command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback to previous version')
    rollback_parser.add_argument('model_name', help='Name of the model to rollback')
    
    # Evaluate model command
    eval_parser = subparsers.add_parser('evaluate', help='Evaluate current model')
    eval_parser.add_argument('--test-data', help='Path to test data file')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old model versions')
    cleanup_parser.add_argument('model_name', help='Name of the model to cleanup')
    cleanup_parser.add_argument('--keep', type=int, default=5, help='Number of versions to keep')
    
    # Performance history command
    perf_parser = subparsers.add_parser('performance', help='Show performance history')
    perf_parser.add_argument('--model', help='Model name (default: all models)')
    
    # Export model command
    export_parser = subparsers.add_parser('export', help='Export a model')
    export_parser.add_argument('model_name', help='Name of the model to export')
    export_parser.add_argument('version_id', help='Version ID to export')
    export_parser.add_argument('output_path', help='Output file path')
    
    # Import model command
    import_parser = subparsers.add_parser('import', help='Import a model')
    import_parser.add_argument('model_path', help='Path to model file')
    import_parser.add_argument('model_name', help='Name for the imported model')
    import_parser.add_argument('--metrics', help='Path to performance metrics JSON file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Initialize CLI
        cli = MLModelManagerCLI(args.models_dir)
        
        # Execute command
        if args.command == 'list':
            cli.list_models()
        elif args.command == 'current':
            cli.show_current_model()
        elif args.command == 'deploy':
            cli.deploy_model(args.model_name, args.version)
        elif args.command == 'rollback':
            cli.rollback_model(args.model_name)
        elif args.command == 'evaluate':
            cli.evaluate_model(args.test_data)
        elif args.command == 'cleanup':
            cli.cleanup_old_versions(args.model_name, args.keep)
        elif args.command == 'performance':
            cli.get_performance_history(args.model)
        elif args.command == 'export':
            cli.export_model(args.model_name, args.version_id, args.output_path)
        elif args.command == 'import':
            metrics = None
            if args.metrics:
                with open(args.metrics, 'r') as f:
                    metrics = json.load(f)
            cli.import_model(args.model_path, args.model_name, metrics)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
