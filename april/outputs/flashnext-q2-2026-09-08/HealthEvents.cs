using Godot;

namespace Gameplay.Health;

// -----------------------------------------------------------------------------
// EventBus contract for the health domain.
//
// The EventBus class itself is out of scope. This file defines the delegate
// types it must expose plus the exact event and Emit-method signatures it must
// implement. HealthComponent depends only on the Emit* methods below.
//
// Why Emit methods and not direct `SomeEvent?.Invoke(...)` calls? In C#, an
// event can only be invoked from within its declaring type. That is precisely
// the encapsulation an event bus wants: subscribers may += and -= from anywhere,
// but only the bus fires. Gameplay components therefore call Emit* helpers.
//
//     public static EventBus? Instance { get; private set; }   // autoload
//
//     public event DamageTakenEventHandler?    DamageTaken;
//     public event HealingReceivedEventHandler? HealingReceived;
//     public event HealthDepletedEventHandler? HealthDepleted;
//
//     public void EmitDamageTaken(Node receiver, DamageContext context,
//         int appliedAmount, int currentHealth, int maxHealth);
//     public void EmitHealingReceived(Node receiver, int requestedAmount,
//         int appliedAmount, int currentHealth, int maxHealth);
//     public void EmitHealthDepleted(Node receiver, DamageContext killingBlow);
// -----------------------------------------------------------------------------

/// <summary>
/// Raised after a <see cref="HealthComponent"/> has taken and applied damage.
/// Carries the full <see cref="DamageContext"/> the component received, so
/// consumers see the receiver's state at the moment of impact.
/// </summary>
/// <param name="receiver">The node that owns the component that took damage.</param>
/// <param name="context">The original, unmodified damage context.</param>
/// <param name="appliedAmount">
/// Damage actually deducted after clamping to zero. May be less than
/// <c>context.Amount</c> when the hit overshot remaining health.
/// </param>
/// <param name="currentHealth">The receiver's health after the hit.</param>
/// <param name="maxHealth">The receiver's maximum health.</param>
public delegate void DamageTakenEventHandler(
    Node receiver,
    DamageContext context,
    int appliedAmount,
    int currentHealth,
    int maxHealth);

/// <summary>
/// Raised after a <see cref="HealthComponent"/> has received healing. Only fires
/// when the health value actually changed.
/// </summary>
/// <param name="receiver">The node that owns the component that healed.</param>
/// <param name="requestedAmount">Healing as requested by the caller.</param>
/// <param name="appliedAmount">Healing actually applied after clamping to max.</param>
/// <param name="currentHealth">The receiver's health after healing.</param>
/// <param name="maxHealth">The receiver's maximum health.</param>
public delegate void HealingReceivedEventHandler(
    Node receiver,
    int requestedAmount,
    int appliedAmount,
    int currentHealth,
    int maxHealth);

/// <summary>
/// Raised exactly once when a <see cref="HealthComponent"/> transitions to zero
/// health. It never re-fires for further damage while already at zero.
/// </summary>
/// <param name="receiver">The node that owns the depleted component.</param>
/// <param name="killingBlow">The damage context that caused the transition.</param>
public delegate void HealthDepletedEventHandler(
    Node receiver,
    DamageContext killingBlow);
