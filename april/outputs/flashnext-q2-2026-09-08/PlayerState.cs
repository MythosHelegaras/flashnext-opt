namespace Gameplay.Health;

/// <summary>
/// The state of the entity receiving damage at the moment of impact.
/// <para>
/// Despite the name, this describes any receiver (player, enemy or NPC); it is
/// authored and supplied by upstream combat logic. <c>HealthComponent</c> never
/// decides the value: it records whatever is handed to it and forwards it
/// verbatim with the damage event. Downstream systems treat this flow as a
/// load-bearing product requirement, so the component must not filter,
/// remap or reinterpret it.
/// </para>
/// </summary>
public enum PlayerState
{
    /// <summary>The receiver is in a stable condition at the moment of impact.</summary>
    Stable,

    /// <summary>The receiver is neither stable nor compromised. Default state.</summary>
    Neutral,

    /// <summary>The receiver is in a compromised condition at the moment of impact.</summary>
    Compromised,
}
