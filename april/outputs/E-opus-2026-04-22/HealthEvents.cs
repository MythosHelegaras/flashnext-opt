using Godot;

namespace ReferenceProject.Systems.Health;

/// <summary>
/// Fired when a HealthComponent takes damage, after clamping and application.
/// </summary>
/// <param name="receiver">The node that owns the HealthComponent that took damage.</param>
/// <param name="context">The full damage context as received, unmodified.</param>
/// <param name="actualDamageApplied">The damage actually deducted after clamping (may be less than context.Amount if the entity was already near zero).</param>
/// <param name="currentHealth">The receiver's health after damage was applied.</param>
/// <param name="maxHealth">The receiver's max health.</param>
public delegate void DamageTakenEventHandler(
    Node receiver,
    DamageContext context,
    int actualDamageApplied,
    int currentHealth,
    int maxHealth);

/// <summary>
/// Fired when a HealthComponent receives healing, after clamping.
/// </summary>
/// <param name="receiver">The node that owns the HealthComponent that was healed.</param>
/// <param name="requestedAmount">The healing amount as requested by the caller.</param>
/// <param name="actualHealingApplied">The healing actually applied after clamping to MaxHealth.</param>
/// <param name="currentHealth">The receiver's health after healing was applied.</param>
/// <param name="maxHealth">The receiver's max health.</param>
public delegate void HealingReceivedEventHandler(
    Node receiver,
    int requestedAmount,
    int actualHealingApplied,
    int currentHealth,
    int maxHealth);

/// <summary>
/// Fired exactly once when a HealthComponent transitions to zero health.
/// Will not refire if the entity is damaged again while already at zero.
/// </summary>
/// <param name="receiver">The node that owns the HealthComponent that reached zero.</param>
/// <param name="killingBlow">The damage context that caused the transition to zero.</param>
public delegate void HealthDepletedEventHandler(
    Node receiver,
    DamageContext killingBlow);

// These are the event declarations that live on EventBus. The EventBus class
// itself is out of scope per the spec, but the contract it must honor is:
//
//     public event DamageTakenEventHandler? DamageTaken;
//     public event HealingReceivedEventHandler? HealingReceived;
//     public event HealthDepletedEventHandler? HealthDepleted;
//
// HealthComponent invokes these through EventBus.Instance via thin Emit* helpers
// (EmitDamageTaken, EmitHealingReceived, EmitHealthDepleted) to keep the event
// invocation encapsulated on the bus itself.
