using Godot;
using ReferenceProject.Autoloads;

namespace ReferenceProject.Systems.Health;

/// <summary>
/// A reusable health container attachable to any entity (player, enemy, NPC).
/// Records damage and healing, clamps values safely, and broadcasts state
/// changes through the global EventBus. Has no direct references to any
/// other gameplay system.
/// </summary>
public partial class HealthComponent : Node
{
    private int _maxHealth = 100;
    private int _currentHealth;
    private bool _isDepleted;

    /// <summary>
    /// The maximum health this entity can have. Tuned per-entity in the editor.
    /// Minimum of 1 — zero-max entities are nonsense and are clamped up.
    /// </summary>
    [Export]
    public int MaxHealth
    {
        get => _maxHealth;
        set
        {
            _maxHealth = Mathf.Max(1, value);
            if (_currentHealth > _maxHealth)
            {
                _currentHealth = _maxHealth;
            }
        }
    }

    /// <summary>
    /// The entity's current health. Runtime state — not editor-exported.
    /// Always within [0, MaxHealth].
    /// </summary>
    public int CurrentHealth => _currentHealth;

    /// <summary>True when CurrentHealth has reached zero and HealthDepleted has already been broadcast.</summary>
    public bool IsDepleted => _isDepleted;

    public override void _Ready()
    {
        _currentHealth = _maxHealth;
        _isDepleted = false;
    }

    /// <summary>
    /// Apply damage to this entity. The context is forwarded verbatim on the
    /// EventBus so downstream systems can reason about the circumstances.
    /// </summary>
    /// <param name="context">
    /// Full damage context. Amount below zero is ignored (logged and dropped).
    /// Zero-amount damage is also dropped without broadcasting — it is not
    /// a meaningful event.
    /// </param>
    public void ApplyDamage(DamageContext context)
    {
        if (_isDepleted)
        {
            // Already dead. Additional hits are dropped silently.
            // If post-death effects are ever needed (overkill tracking, corpse
            // desecration mechanics), they belong in a separate component.
            return;
        }

        if (context.Amount < 0)
        {
            GD.PushWarning($"HealthComponent on {GetParent()?.Name ?? Name}: negative damage amount ({context.Amount}) ignored.");
            return;
        }

        if (context.Amount == 0)
        {
            return;
        }

        int healthBefore = _currentHealth;
        _currentHealth = Mathf.Max(0, _currentHealth - context.Amount);
        int actualApplied = healthBefore - _currentHealth;

        Node receiver = GetParent() ?? this;

        EventBus.Instance.EmitDamageTaken(
            receiver,
            context,
            actualApplied,
            _currentHealth,
            _maxHealth);

        if (_currentHealth == 0)
        {
            _isDepleted = true;
            EventBus.Instance.EmitHealthDepleted(receiver, context);
        }
    }

    /// <summary>
    /// Apply healing to this entity. Cannot heal past MaxHealth.
    /// Cannot heal an entity that has already reached zero — resurrection
    /// is a distinct concept and does not belong in a generic health component.
    /// </summary>
    /// <param name="amount">Requested healing. Negative and zero values are dropped.</param>
    public void ApplyHealing(int amount)
    {
        if (_isDepleted)
        {
            // The dead do not heal. Revival is out of scope.
            return;
        }

        if (amount < 0)
        {
            GD.PushWarning($"HealthComponent on {GetParent()?.Name ?? Name}: negative healing amount ({amount}) ignored.");
            return;
        }

        if (amount == 0)
        {
            return;
        }

        int healthBefore = _currentHealth;
        _currentHealth = Mathf.Min(_maxHealth, _currentHealth + amount);
        int actualApplied = _currentHealth - healthBefore;

        if (actualApplied == 0)
        {
            // Already at full. Don't broadcast a no-op.
            return;
        }

        Node receiver = GetParent() ?? this;

        EventBus.Instance.EmitHealingReceived(
            receiver,
            amount,
            actualApplied,
            _currentHealth,
            _maxHealth);
    }
}
