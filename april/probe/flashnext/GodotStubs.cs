// Minimal stand-ins for the Godot API surface the published files touch, plus the
// EventBus contract exactly as HealthEvents.cs describes it. No game logic here.
namespace Godot {
  public class ExportAttribute : System.Attribute {}
  public class Node { public string Name {get;set;} = "Entity"; public Node? Parent; public virtual void _Ready(){} public Node? GetParent()=>Parent; }
  public static class GD { public static void PushWarning(string s)=>System.Console.WriteLine("warn: "+s); }
}
namespace Gameplay.Health {
  using Godot;
  // EventBus exactly per the contract in HealthEvents.cs
  public partial class EventBus : Node {
    public static EventBus? Instance {get; private set;} = new EventBus();
    public event DamageTakenEventHandler? DamageTaken; public event HealingReceivedEventHandler? HealingReceived; public event HealthDepletedEventHandler? HealthDepleted;
    public void EmitDamageTaken(Node r, DamageContext c, int a, int cur, int max)=>DamageTaken?.Invoke(r,c,a,cur,max);
    public void EmitHealingReceived(Node r, int q, int a, int cur, int max)=>HealingReceived?.Invoke(r,q,a,cur,max);
    public void EmitHealthDepleted(Node r, DamageContext k)=>HealthDepleted?.Invoke(r,k);
  }
}
