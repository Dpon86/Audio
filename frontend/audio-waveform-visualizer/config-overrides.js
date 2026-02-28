module.exports = function override(config, env) {
  // Disable CSS minimization to avoid pseudo-element parsing errors
  if (config.optimization && config.optimization.minimizer) {
    config.optimization.minimizer = config.optimization.minimizer.filter(
      plugin => {
        // Remove CssMinimizerPlugin
        return !(plugin.constructor && plugin.constructor.name === 'CssMinimizerPlugin');
      }
    );
  }
  
  return config;
};
