const defaultBettingRules = (match, team, country, league) => [
  {
    ruleType: "goals",  // Rule type for goals-related conditions
    odds: {
      min: 1.01,
      max: 1.05
    },
    active: true,
    // Strategy-specific parameters
    match: match,
    country: country,
    league: league,
    // Goals-specific conditions
    minGoals: 1,  // Minimum total goals required for the rule to apply (e.g., don't bet if 0-0)
    maxGoals: 3,  // Maximum total goals allowed for the rule to apply (e.g., don't bet if score is already high)
    // goalMargin: 3.5 // Removed - Replaced by buffer logic in strategy
    minGoalLineBuffer: 2.5 // Optional: Minimum buffer for selecting the standard goal line (e.g., target line >= score + buffer)
  },
  {
    ruleType: "stake",  // Rule type for stake-related parameters
    active: true,
    stake: 0.50,      // Amount to stake
    // Additional stake parameters could be added here
    stakeStrategy: "fixed",  // Alternative could be "percentage", "kelly", etc.
  },
  {
    ruleType: "divisor", // Rule type for divisor-related parameters
    active: true,
    divisor: 8,      // Divisor used for stake calculations when using balance
  },
  {
    ruleType: "time",  // Rule type for time-related conditions
    active: true,
    // Time-specific conditions
    // Example: Shifted window later in the match (e.g., 65-75 minutes)
    minMinute: 65,  // Increased minimum minute
    maxMinute: 75,  // Adjusted maximum minute
  },
  // Additional rules can be added as needed
  // Example composite rule:
  {
    ruleType: "composite",
    active: true,
    conditions: [
      { type: "goals", comparison: "<=", value: 3 },
      { type: "time", comparison: "between", min: 52, max: 61 }
    ]
  }
]

module.exports = { defaultBettingRules };
