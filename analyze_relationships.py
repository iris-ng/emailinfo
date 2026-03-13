"""
Email Sender-Recipient Relationship Analysis

This program analyzes sender-recipient relationships from extracted email data.
It handles various email format inconsistencies and generates three types of outputs:
- Option A: Detailed CSV with all sender-recipient pairs
- Option B: Network graph data (nodes and edges)
- Option C: Summary statistics and top relationships
"""

import pandas as pd
import re
from collections import defaultdict, Counter
from pathlib import Path
import json


class EmailParser:
    """Handles parsing and normalization of email addresses and names."""

    @staticmethod
    def parse_email_field(field):
        """
        Parse email field to extract name and email address.

        Handles formats:
        - 'Name' <email@domain.com>
        - Name <email@domain.com>
        - <email@domain.com>
        - email@domain.com
        - Name (no email)

        Returns: (name, email) tuple where either can be None
        """
        if pd.isna(field) or field == '':
            return None, None

        field = str(field).strip()

        # Pattern 1: Name <email@domain.com> or 'Name' <email@domain.com>
        match = re.search(r"(['\"]?)([^'\"<>]+)\1\s*<([^>]+)>", field)
        if match:
            name = match.group(2).strip()
            email = match.group(3).strip().lower()
            return name, email

        # Pattern 2: <email@domain.com>
        match = re.search(r"<([^>]+)>", field)
        if match:
            email = match.group(1).strip().lower()
            return None, email

        # Pattern 3: Just email (contains @)
        if '@' in field:
            email = field.strip().lower()
            return None, email

        # Pattern 4: Just name (no email)
        name = field.strip()
        return name, None

    @staticmethod
    def get_identifier(name, email):
        """
        Create a unique identifier for a person.
        Prefer email address; fallback to normalized name.
        """
        if email:
            return email
        elif name:
            # Normalize name: lowercase, remove extra spaces
            return name.lower().strip()
        return None

    @staticmethod
    def split_recipients(field):
        """
        Split a field containing multiple recipients separated by semicolons.
        Returns list of (name, email) tuples.
        """
        if pd.isna(field) or field == '':
            return []

        field = str(field)
        # Split by semicolon
        recipients = field.split(';')

        parsed = []
        for recipient in recipients:
            recipient = recipient.strip()
            if recipient:
                name, email = EmailParser.parse_email_field(recipient)
                if name or email:
                    parsed.append((name, email))

        return parsed


class PersonRegistry:
    """Maintains a registry of unique people with their various name representations."""

    def __init__(self):
        self.identifier_to_names = defaultdict(Counter)  # identifier -> {name: count}
        self.identifier_to_email = {}  # identifier -> email (if identifier is email)

    def register_person(self, name, email):
        """Register a person and track their name variations."""
        identifier = EmailParser.get_identifier(name, email)
        if not identifier:
            return None

        # Track email if identifier is an email
        if email and identifier == email:
            self.identifier_to_email[identifier] = email

        # Track name variation
        if name:
            self.identifier_to_names[identifier][name] += 1

        return identifier

    def get_display_name(self, identifier):
        """Get the most common/best display name for an identifier."""
        if not identifier:
            return "Unknown"

        # If we have name variations, use the most common one
        if identifier in self.identifier_to_names and self.identifier_to_names[identifier]:
            # Get most common name
            most_common_name = self.identifier_to_names[identifier].most_common(1)[0][0]
            return most_common_name

        # Otherwise return the identifier itself
        return identifier

    def get_email(self, identifier):
        """Get email address for an identifier (if it exists)."""
        return self.identifier_to_email.get(identifier, identifier if '@' in str(identifier) else None)


class RelationshipAnalyzer:
    """Analyzes sender-recipient relationships from email data."""

    def __init__(self, excel_file):
        self.df = pd.read_excel(excel_file)
        self.person_registry = PersonRegistry()
        self.relationships = defaultdict(int)  # (sender_id, recipient_id) -> count
        self.sender_counts = Counter()  # sender_id -> total emails sent
        self.recipient_counts = Counter()  # recipient_id -> total emails received

    def analyze(self):
        """Main analysis function."""
        print(f"Analyzing {len(self.df)} emails...")

        for idx, row in self.df.iterrows():
            # Parse sender
            sender_name, sender_email = EmailParser.parse_email_field(row['sender'])
            sender_id = self.person_registry.register_person(sender_name, sender_email)

            if not sender_id:
                continue

            self.sender_counts[sender_id] += 1

            # Parse recipients from TO field
            to_recipients = EmailParser.split_recipients(row['recipient'])

            # Parse recipients from CC field
            cc_recipients = EmailParser.split_recipients(row['cc'])

            # Combine all recipients
            all_recipients = to_recipients + cc_recipients

            # Register each recipient and track relationship
            for recip_name, recip_email in all_recipients:
                recip_id = self.person_registry.register_person(recip_name, recip_email)

                if recip_id:
                    # Track relationship
                    self.relationships[(sender_id, recip_id)] += 1
                    self.recipient_counts[recip_id] += 1

        print(f"Found {len(self.person_registry.identifier_to_names)} unique people")
        print(f"Found {len(self.relationships)} unique sender-recipient pairs")

    def generate_detailed_csv(self, output_file='relationship_details.csv'):
        """Option A: Generate detailed CSV with all sender-recipient pairs."""
        print(f"\nGenerating detailed CSV: {output_file}")

        rows = []
        for (sender_id, recipient_id), count in self.relationships.items():
            rows.append({
                'sender_email': self.person_registry.get_email(sender_id),
                'sender_name': self.person_registry.get_display_name(sender_id),
                'sender_identifier': sender_id,
                'recipient_email': self.person_registry.get_email(recipient_id),
                'recipient_name': self.person_registry.get_display_name(recipient_id),
                'recipient_identifier': recipient_id,
                'email_count': count
            })

        df = pd.DataFrame(rows)
        df = df.sort_values('email_count', ascending=False)
        df.to_csv(output_file, index=False)

        print(f"✓ Saved {len(df)} sender-recipient pairs to {output_file}")
        return df

    def generate_network_graph(self, nodes_file='network_nodes.csv', edges_file='network_edges.csv'):
        """Option B: Generate network graph data (nodes and edges)."""
        print(f"\nGenerating network graph data...")

        # Generate nodes
        all_people = set()
        for sender_id, recipient_id in self.relationships.keys():
            all_people.add(sender_id)
            all_people.add(recipient_id)

        nodes = []
        for person_id in all_people:
            nodes.append({
                'id': person_id,
                'label': self.person_registry.get_display_name(person_id),
                'email': self.person_registry.get_email(person_id),
                'emails_sent': self.sender_counts.get(person_id, 0),
                'emails_received': self.recipient_counts.get(person_id, 0),
                'total_activity': self.sender_counts.get(person_id, 0) + self.recipient_counts.get(person_id, 0)
            })

        nodes_df = pd.DataFrame(nodes)
        nodes_df = nodes_df.sort_values('total_activity', ascending=False)
        nodes_df.to_csv(nodes_file, index=False)

        # Generate edges
        edges = []
        for (sender_id, recipient_id), count in self.relationships.items():
            edges.append({
                'source': sender_id,
                'target': recipient_id,
                'weight': count,
                'source_label': self.person_registry.get_display_name(sender_id),
                'target_label': self.person_registry.get_display_name(recipient_id)
            })

        edges_df = pd.DataFrame(edges)
        edges_df = edges_df.sort_values('weight', ascending=False)
        edges_df.to_csv(edges_file, index=False)

        print(f"✓ Saved {len(nodes_df)} nodes to {nodes_file}")
        print(f"✓ Saved {len(edges_df)} edges to {edges_file}")

        return nodes_df, edges_df

    def generate_summary_report(self, output_file='relationship_summary.txt', top_n=20):
        """Option C: Generate summary statistics and top relationships."""
        print(f"\nGenerating summary report: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("EMAIL SENDER-RECIPIENT RELATIONSHIP ANALYSIS SUMMARY\n")
            f.write("=" * 80 + "\n\n")

            # Overall statistics
            f.write("OVERALL STATISTICS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total emails analyzed: {len(self.df)}\n")
            f.write(f"Unique people identified: {len(self.person_registry.identifier_to_names)}\n")
            f.write(f"Unique sender-recipient pairs: {len(self.relationships)}\n")
            f.write(f"Total senders: {len(self.sender_counts)}\n")
            f.write(f"Total recipients: {len(self.recipient_counts)}\n")
            f.write("\n")

            # Top senders
            f.write(f"TOP {top_n} MOST ACTIVE SENDERS\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<6} {'Emails Sent':<15} {'Name':<30} {'Email'}\n")
            f.write("-" * 80 + "\n")

            for rank, (sender_id, count) in enumerate(self.sender_counts.most_common(top_n), 1):
                name = self.person_registry.get_display_name(sender_id)
                email = self.person_registry.get_email(sender_id) or "N/A"
                f.write(f"{rank:<6} {count:<15} {name:<30} {email}\n")
            f.write("\n")

            # Top recipients
            f.write(f"TOP {top_n} MOST CONTACTED RECIPIENTS\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<6} {'Emails Received':<15} {'Name':<30} {'Email'}\n")
            f.write("-" * 80 + "\n")

            for rank, (recip_id, count) in enumerate(self.recipient_counts.most_common(top_n), 1):
                name = self.person_registry.get_display_name(recip_id)
                email = self.person_registry.get_email(recip_id) or "N/A"
                f.write(f"{rank:<6} {count:<15} {name:<30} {email}\n")
            f.write("\n")

            # Top sender-recipient pairs
            f.write(f"TOP {top_n} SENDER-RECIPIENT PAIRS (Who talks to whom most often?)\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Rank':<6} {'Count':<8} {'Sender':<25} {'→ Recipient'}\n")
            f.write("-" * 80 + "\n")

            sorted_pairs = sorted(self.relationships.items(), key=lambda x: x[1], reverse=True)
            for rank, ((sender_id, recip_id), count) in enumerate(sorted_pairs[:top_n], 1):
                sender_name = self.person_registry.get_display_name(sender_id)
                recip_name = self.person_registry.get_display_name(recip_id)
                f.write(f"{rank:<6} {count:<8} {sender_name:<25} → {recip_name}\n")
            f.write("\n")

            # Communication matrix - top communicators
            f.write("COMMUNICATION INTENSITY ANALYSIS\n")
            f.write("-" * 80 + "\n")

            # Find people who both send and receive a lot
            both_active = []
            for person_id in self.person_registry.identifier_to_names.keys():
                sent = self.sender_counts.get(person_id, 0)
                received = self.recipient_counts.get(person_id, 0)
                if sent > 0 or received > 0:
                    both_active.append((person_id, sent, received, sent + received))

            both_active.sort(key=lambda x: x[3], reverse=True)

            f.write(f"{'Name':<30} {'Sent':<12} {'Received':<12} {'Total'}\n")
            f.write("-" * 80 + "\n")
            for person_id, sent, received, total in both_active[:top_n]:
                name = self.person_registry.get_display_name(person_id)
                f.write(f"{name:<30} {sent:<12} {received:<12} {total}\n")

            f.write("\n")
            f.write("=" * 80 + "\n")

        print(f"✓ Saved summary report to {output_file}")

        # Also create a JSON version for programmatic access
        summary_json = {
            'statistics': {
                'total_emails': len(self.df),
                'unique_people': len(self.person_registry.identifier_to_names),
                'unique_pairs': len(self.relationships),
                'total_senders': len(self.sender_counts),
                'total_recipients': len(self.recipient_counts)
            },
            'top_senders': [
                {
                    'identifier': sender_id,
                    'name': self.person_registry.get_display_name(sender_id),
                    'email': self.person_registry.get_email(sender_id),
                    'count': count
                }
                for sender_id, count in self.sender_counts.most_common(top_n)
            ],
            'top_recipients': [
                {
                    'identifier': recip_id,
                    'name': self.person_registry.get_display_name(recip_id),
                    'email': self.person_registry.get_email(recip_id),
                    'count': count
                }
                for recip_id, count in self.recipient_counts.most_common(top_n)
            ],
            'top_pairs': [
                {
                    'sender': {
                        'identifier': sender_id,
                        'name': self.person_registry.get_display_name(sender_id),
                        'email': self.person_registry.get_email(sender_id)
                    },
                    'recipient': {
                        'identifier': recip_id,
                        'name': self.person_registry.get_display_name(recip_id),
                        'email': self.person_registry.get_email(recip_id)
                    },
                    'count': count
                }
                for (sender_id, recip_id), count in sorted_pairs[:top_n]
            ]
        }

        json_file = Path(output_file).with_suffix('.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(summary_json, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved summary JSON to {json_file}")


def run(excel_file=None, output_dir='output', top_n=20):
    """Importable entry point — runs the full analysis and writes output files."""
    out = Path(output_dir)
    if excel_file is None:
        excel_file = out / 'results.xlsx'
    analyzer = RelationshipAnalyzer(excel_file)
    analyzer.analyze()
    analyzer.generate_detailed_csv(out / 'relationship_details.csv')
    analyzer.generate_network_graph(out / 'network_nodes.csv', out / 'network_edges.csv')
    analyzer.generate_summary_report(out / 'relationship_summary.txt', top_n=top_n)


def main():
    """Main entry point for the analysis."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze email sender-recipient relationships')
    parser.add_argument('--input', default='results.xlsx', help='Input Excel file (default: results.xlsx)')
    parser.add_argument('--top-n', type=int, default=20, help='Number of top items to show in summary (default: 20)')

    args = parser.parse_args()

    print("=" * 80)
    print("EMAIL SENDER-RECIPIENT RELATIONSHIP ANALYZER")
    print("=" * 80)
    print()

    # Create analyzer
    analyzer = RelationshipAnalyzer(args.input)

    # Run analysis
    analyzer.analyze()

    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)

    # Generate all three output types
    analyzer.generate_detailed_csv('relationship_details.csv')
    analyzer.generate_network_graph('network_nodes.csv', 'network_edges.csv')
    analyzer.generate_summary_report('relationship_summary.txt', top_n=args.top_n)

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE!")
    print("=" * 80)
    print("\nGenerated files:")
    print("  • relationship_details.csv - Detailed sender-recipient pairs (Option A)")
    print("  • network_nodes.csv - Network graph nodes (Option B)")
    print("  • network_edges.csv - Network graph edges (Option B)")
    print("  • relationship_summary.txt - Human-readable summary report (Option C)")
    print("  • relationship_summary.json - Machine-readable summary data (Option C)")
    print()


if __name__ == '__main__':
    main()
