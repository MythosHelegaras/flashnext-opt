using Godot;

namespace Gameplay.Health;

/// <summary>
/// An immutable description of a single damage instance. Created by the caller,
/// passed into <see cref="HealthComponent.ApplyDamage"/>, and forwarded
/// unchanged on the <c>EventBus</c> so downstream systems can reason about the
/// circumstances of the hit, not just its magnitude.
/// </summary>
/// <remarks>
/// A <c>readonly record struct</c> is used deliberately: contexts are allocated
/// per hit, forwarded once, and must not be mutated after construction. Value
/// semantics guarantee no handler can alter what another handler observes. The
/// component performs no validation here — the context records what was
/// <em>requested</em>; clamping happens when the component applies it.
/// </remarks>
public readonly record struct DamageContext
{
    /// <summary>
    /// Damage amount requested by the source. Must be non-negative; a negative
    /// value is treated as invalid input and dropped by the component.
    /// </summary>
    public int Amount { get; init; }

    /// <summary>
    /// The originating entity, or <c>null</c> for sourceless damage such as
    /// environmental hazards or self-inflicted effects.
    /// </summary>
    public Node? Source { get; init; }

    /// <summary>
    /// The receiver's <see cref="PlayerState"/> at the moment of impact. This is
    /// the load-bearing field: it must survive the round trip from caller to
    /// event consumer without being altered.
    /// </summary>
    public PlayerState ReceiverState { get; init; }

    /// <summary>Constructs a damage context.</summary>
    /// <param name="amount">Requested, non-negative damage amount.</param>
    /// <param name="source">Originating entity, or <c>null</c> if sourceless.</param>
    /// <param name="receiverState">The receiver's state at the moment of impact.</param>
    public DamageContext(int amount, Node? source, PlayerState receiverState)
    {
        Amount = amount;
        Source = source;
        ReceiverState = receiverState;
    }
}
