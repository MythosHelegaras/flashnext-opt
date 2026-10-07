using System;
using Godot;

namespace Gameplay.Health;

/// <summary>
/// A reusable health container attachable to any entity (player, enemy or NPC).
/// <para>
/// It applies damage and healing, clamps its values safely, and broadcasts every
/// state change through the global <c>EventBus</c>. It holds no references to any
/// other gameplay system and performs no sibling lookups: the bus is its sole
/// point of contact with the rest of the game.
/// </para>
/// </summary>
public partial class HealthComponent : Node
{
    private const int DefaultMaxHealth = 100;

    private int _maxHealth = DefaultMaxHealth;
    private int _currentHealth = DefaultMaxHealth;
    private bool _isDepleted;

    /// <summary>
    /// The maximum health this entity can have, tunable per-entity in the editor.
    /// Clamped to a minimum of 1; lowering it below <see cref="CurrentHealth"/>
    /// also reduces current health to match.
    /// </summary>
    [Export]
    public int MaxHealth
    {
        get => _maxHealth;
        set
        {
            _maxHealth = Math.Max(1, value);
            if (_currentHealth > _maxHealth)
            {
                _currentHealth = _maxHealth;
            }
        }
    }

    /// <summary>
    /// The entity's current health, within <c>[0, MaxHealth]</c>. Tunable in the
    /// editor to author a non-full starting value. Runtime changes must go through
    /// <see cref="ApplyDamage"/> or <see cref="ApplyHealing"/> so the matching
    /// <c>EventBus</c> events fire; direct assignment (editor or debugger) is
    /// clamped into range and intentionally emits nothing.
    /// </summary>
    [Export]
    public int CurrentHealth
    {
        get => _currentHealth;
        set
        {
            _currentHealth = Math.Clamp(value, 0, _maxHealth);
            _isDepleted = _currentHealth == 0;
        }
    }

    /// <summary>Whether this entity has reached zero health and broadcast depletion.</summary>
    public bool IsDepleted => _isDepleted;

    /// <summary>
    /// Normalises serialized state on entry to the scene tree without emitting
    /// events, since subscribers may not be connected yet during load.
    /// </summary>
    public override void _Ready()
    {
        _currentHealth = Math.Clamp(_currentHealth, 0, _maxHealth);
        _isDepleted = _currentHealth == 0;
    }

    /// <summary>
    /// Applies damage to this entity. The supplied <paramref name="context"/> is
    /// forwarded verbatim on the <c>EventBus</c>, so the receiver's
    /// <see cref="PlayerState"/> recorded at the moment of impact reaches
    /// downstream systems unchanged.
    /// </summary>
    /// <param name="context">
    /// The damage context. A negative <c>Amount</c> is invalid input and is
    /// dropped with a warning. Zero-amount damage is dropped silently. Once the
    /// entity is depleted, further damage is ignored (overkill effects belong in
    /// a dedicated component, not here).
    /// </param>
    public void ApplyDamage(DamageContext context)
    {
        if (_isDepleted)
        {
            return;
        }

        if (context.Amount <= 0)
        {
            if (context.Amount < 0)
            {
                GD.PushWarning(
                    $"HealthComponent on '{DescribeOwner()}' received negative damage " +
                    $"({context.Amount}); ignored.");
            }

            return;
        }

        int healthBefore = _currentHealth;
        _currentHealth = Math.Max(0, healthBefore - context.Amount);
        int applied = healthBefore - _currentHealth;

        Node receiver = GetParent() ?? this;
        EventBus.Instance.EmitDamageTaken(receiver, context, applied, _currentHealth, _maxHealth);

        if (_currentHealth == 0)
        {
            _isDepleted = true;
            EventBus.Instance.EmitHealthDepleted(receiver, context);
        }
    }

    /// <summary>
    /// Applies healing to this entity, clamped so it never exceeds
    /// <see cref="MaxHealth"/>. An entity already at zero cannot be healed:
    /// resurrection is a distinct mechanic and intentionally out of scope.
    /// </summary>
    /// <param name="amount">
    /// Requested healing. A negative value is invalid input and is dropped with a
    /// warning. Zero, or healing that produces no actual change (already at max),
    /// emits nothing.
    /// </param>
    public void ApplyHealing(int amount)
    {
        if (_isDepleted)
        {
            return;
        }

        if (amount <= 0)
        {
            if (amount < 0)
            {
                GD.PushWarning(
                    $"HealthComponent on '{DescribeOwner()}' received negative healing " +
                    $"({amount}); ignored.");
            }

            return;
        }

        int healthBefore = _currentHealth;
        // Clamp before adding: avoids int overflow for a pathologically large
        // amount while keeping the result within [healthBefore, MaxHealth].
        _currentHealth = healthBefore + Math.Min(amount, _maxHealth - healthBefore);
        int applied = _currentHealth - healthBefore;

        if (applied == 0)
        {
            return;
        }

        Node receiver = GetParent() ?? this;
        EventBus.Instance.EmitHealingReceived(receiver, amount, applied, _currentHealth, _maxHealth);
    }

    /// <summary>Returns the owning entity's name for diagnostics, falling back to this node.</summary>
    private string DescribeOwner()
    {
        Node? owner = GetParent();
        return owner is not null ? owner.Name.ToString() : Name.ToString();
    }
}
